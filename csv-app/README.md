# CSV Processor Web App

A lightweight Flask web application that:

- **Uploads & parses** CSV files through a drag-and-drop browser interface
- **Displays** all file contents in a searchable, paginated table
- **Archives** each processed file to Amazon S3
- **Automatically applies** an S3 Lifecycle policy that transitions objects through Glacier tiers

---

## Quick Start

```bash
cd csv-app
pip install -r requirements.txt

# Copy and fill in your credentials
cp .env.example .env
# edit .env

export $(grep -v '^#' .env | xargs)
python app.py
# Open http://localhost:5000
```

### Docker

```bash
docker build -t csv-processor .
docker run -p 5000:5000 --env-file .env csv-processor
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `S3_BUCKET` | ✅ | — | Target S3 bucket name |
| `AWS_ACCESS_KEY_ID` | ✅ | — | IAM access key |
| `AWS_SECRET_ACCESS_KEY` | ✅ | — | IAM secret key |
| `AWS_SESSION_TOKEN` | — | — | Only for STS/assumed-role creds |
| `AWS_REGION` | — | `us-east-1` | AWS region |
| `S3_PREFIX` | — | `csv-uploads/` | Key prefix (folder) in the bucket |
| `GLACIER_TRANSITION_DAYS` | — | `30` | Days before first Glacier transition |
| `SECRET_KEY` | — | dev default | Flask session secret |
| `PORT` | — | `5000` | Listening port |

---

## S3 Glacier Lifecycle Policy

Every time a file is uploaded the app **idempotently** applies (or refreshes) a
lifecycle rule to the bucket prefix. The rule is non-destructive — it only
adds/replaces the `csv-app-glacier-transition` rule ID and leaves any other
rules untouched.

### Transition ladder

```
Day 0          → STANDARD  (uploaded, immediately accessible)
Day +N         → GLACIER_IR (Glacier Instant Retrieval — ms latency, ~68% cheaper)
Day +N + 90    → DEEP_ARCHIVE (Glacier Deep Archive — lowest cost, 12-48h restore)
```

`N` is controlled by `GLACIER_TRANSITION_DAYS` (default 30).

### Why two tiers?

| Tier | Retrieval | $/GB-month | Best for |
|---|---|---|---|
| S3 Standard | Instant | ~$0.023 | Active data |
| Glacier Instant Retrieval | Milliseconds | ~$0.004 | Infrequent access, compliance |
| Glacier Deep Archive | 12–48 h | ~$0.00099 | Long-term cold storage |

### IAM permissions required

```json
{
  "Effect": "Allow",
  "Action": [
    "s3:PutObject",
    "s3:GetBucketLifecycleConfiguration",
    "s3:PutLifecycleConfiguration"
  ],
  "Resource": [
    "arn:aws:s3:::YOUR_BUCKET",
    "arn:aws:s3:::YOUR_BUCKET/*"
  ]
}
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Upload UI + history |
| `POST` | `/upload` | Process a CSV file |
| `GET` | `/api/files` | JSON list of all processed files |
| `GET` | `/api/file/<id>` | JSON for one file + its parsed content |

---

## CSV Format

The app auto-detects whether the first row is a header by checking if the
first cell is numeric. For header-less files (like the sample) it generates
`Column 1`, `Column 2`, … labels.

Sample format:

```
"211627629","Purple Safi Kaftan","4900.0000"
"211627628","Multi-coloured Gilet Abaya","4900.0000"
```
