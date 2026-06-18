import os
import csv
import json
import boto3
import logging
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, request, render_template, jsonify, redirect, url_for, flash
from werkzeug.utils import secure_filename
from botocore.exceptions import ClientError, NoCredentialsError

# ── Config ────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")

UPLOAD_FOLDER   = Path("uploads")
PROCESSED_LOG   = Path("processed_files.json")
ALLOWED_EXTENSIONS = {"csv"}

UPLOAD_FOLDER.mkdir(exist_ok=True)

# AWS / S3 settings (set via env vars or .env)
S3_BUCKET        = os.environ.get("S3_BUCKET", "")
S3_REGION        = os.environ.get("S3_REGION", "us-east-1")
S3_PREFIX        = os.environ.get("S3_PREFIX", "csv-uploads/")
GLACIER_DAYS     = int(os.environ.get("GLACIER_TRANSITION_DAYS", "30"))

app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

# ── Helpers ───────────────────────────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def load_processed_log() -> list[dict]:
    if PROCESSED_LOG.exists():
        with open(PROCESSED_LOG) as f:
            return json.load(f)
    return []


def save_processed_log(records: list[dict]) -> None:
    with open(PROCESSED_LOG, "w") as f:
        json.dump(records, f, indent=2)


def parse_csv(filepath: str) -> tuple[list[str], list[list[str]]]:
    """Return (headers, rows). Handles files without a header row and blank lines."""
    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        raw = [row for row in reader if any(cell.strip() for cell in row)]  # skip blank rows

    if not raw:
        return [], []

    # Detect if first row looks like a header (non-numeric first cell)
    first = raw[0]
    try:
        float(first[0])
        has_header = False
    except (ValueError, IndexError):
        has_header = True

    if has_header:
        headers = first
        rows    = raw[1:]
    else:
        headers = [f"Column {i+1}" for i in range(len(first))]
        rows    = raw

    return headers, rows


def get_s3_client():
    return boto3.client(
        "s3",
        region_name=S3_REGION,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        aws_session_token=os.environ.get("AWS_SESSION_TOKEN"),
    )


def ensure_lifecycle_policy(s3, bucket: str, prefix: str, days: int) -> dict:
    """
    Idempotently set an S3 lifecycle rule that:
      1. Transitions objects to S3 Glacier Instant Retrieval after `days` days.
      2. Then transitions to S3 Glacier Deep Archive after 90 more days.
    Returns a status dict.
    """
    rule_id = "csv-app-glacier-transition"
    new_rule = {
        "ID": rule_id,
        "Status": "Enabled",
        "Filter": {"Prefix": prefix},
        "Transitions": [
            {
                "Days": days,
                "StorageClass": "GLACIER_IR",   # Glacier Instant Retrieval
            },
            {
                "Days": days + 90,
                "StorageClass": "DEEP_ARCHIVE",  # Glacier Deep Archive
            },
        ],
    }

    # Fetch existing config so we don't wipe other rules
    try:
        existing = s3.get_bucket_lifecycle_configuration(Bucket=bucket)
        rules = existing.get("Rules", [])
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchLifecycleConfiguration":
            rules = []
        else:
            raise

    # Replace or append our rule
    rules = [r for r in rules if r.get("ID") != rule_id]
    rules.append(new_rule)

    s3.put_bucket_lifecycle_configuration(
        Bucket=bucket,
        LifecycleConfiguration={"Rules": rules},
    )
    logger.info("Lifecycle policy applied: Glacier IR after %d days, Deep Archive after %d days", days, days + 90)
    return {
        "applied": True,
        "rule_id": rule_id,
        "glacier_ir_after_days": days,
        "deep_archive_after_days": days + 90,
        "prefix": prefix,
    }


def upload_to_s3(local_path: str, filename: str) -> dict:
    """Upload file to S3, then ensure lifecycle policy is in place."""
    if not S3_BUCKET:
        return {"success": False, "error": "S3_BUCKET env var not set"}

    try:
        s3 = get_s3_client()
        s3_key = f"{S3_PREFIX}{filename}"

        # Upload
        s3.upload_file(
            local_path,
            S3_BUCKET,
            s3_key,
            ExtraArgs={"ContentType": "text/csv"},
        )
        s3_uri = f"s3://{S3_BUCKET}/{s3_key}"
        logger.info("Uploaded %s → %s", filename, s3_uri)

        # Apply / refresh lifecycle policy
        lifecycle = ensure_lifecycle_policy(s3, S3_BUCKET, S3_PREFIX, GLACIER_DAYS)

        return {
            "success": True,
            "bucket":  S3_BUCKET,
            "key":     s3_key,
            "uri":     s3_uri,
            "lifecycle": lifecycle,
        }

    except NoCredentialsError:
        return {"success": False, "error": "AWS credentials not configured"}
    except ClientError as e:
        return {"success": False, "error": str(e)}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    records = load_processed_log()
    s3_configured = bool(S3_BUCKET)
    return render_template("index.html",
                           records=records,
                           s3_configured=s3_configured,
                           s3_bucket=S3_BUCKET,
                           glacier_days=GLACIER_DAYS)


@app.route("/upload", methods=["POST"])
def upload():
    if "csv_file" not in request.files:
        flash("No file selected.", "error")
        return redirect(url_for("index"))

    file = request.files["csv_file"]
    if file.filename == "":
        flash("No file selected.", "error")
        return redirect(url_for("index"))

    if not allowed_file(file.filename):
        flash("Only CSV files are allowed.", "error")
        return redirect(url_for("index"))

    filename  = secure_filename(file.filename)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    unique_fn = f"{timestamp}_{filename}"
    save_path = str(UPLOAD_FOLDER / unique_fn)
    file.save(save_path)

    # Parse
    headers, rows = parse_csv(save_path)

    # Upload to S3
    s3_result = upload_to_s3(save_path, unique_fn)

    # Log
    record = {
        "id":          unique_fn,
        "original_name": filename,
        "saved_as":    unique_fn,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "row_count":   len(rows),
        "columns":     headers,
        "s3":          s3_result,
    }
    records = load_processed_log()
    records.insert(0, record)
    save_processed_log(records)

    return render_template("result.html",
                           record=record,
                           headers=headers,
                           rows=rows,
                           s3_result=s3_result)


@app.route("/api/files")
def api_files():
    return jsonify(load_processed_log())


@app.route("/api/file/<file_id>")
def api_file(file_id):
    records = load_processed_log()
    record  = next((r for r in records if r["id"] == file_id), None)
    if not record:
        return jsonify({"error": "Not found"}), 404

    path = str(UPLOAD_FOLDER / record["saved_as"])
    if not Path(path).exists():
        return jsonify({"error": "File not on disk"}), 404

    headers, rows = parse_csv(path)
    return jsonify({"record": record, "headers": headers, "rows": rows})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
