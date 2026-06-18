FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create non-root user with bash shell
RUN apt-get update && \
    apt-get install -y --no-install-recommends bash && \
    rm -rf /var/lib/apt/lists/* && \
    useradd -m -s /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

ENV PORT=5000
EXPOSE 5000

CMD ["python", "app.py"]



# FROM python:3.12-slim

# WORKDIR /app

# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# COPY . .

# # Non-root user for security
# RUN useradd -m appuser && chown -R appuser /app
# USER appuser

# ENV PORT=5000
# EXPOSE 5000

# CMD ["python", "app.py"]
