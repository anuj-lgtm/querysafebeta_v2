# QuerySafe Deployment Guide

> **Last Updated:** February 2026
> **Method:** Docker-based Cloud Run deployment via `gcloud run deploy --source .`

---

## Architecture Overview

```
QuerySafe Production Stack
+------------------------------------------+
|  Google Cloud Run (asia-south1)          |
|  - Service: querysafe-v2                 |
|  - Image: Python 3.13-slim + Dockerfile  |
|  - Gunicorn: 2 workers, 300s timeout     |
|  - CPU Boost: enabled                    |
|  - Memory: 1Gi, CPU: 1                  |
|  - Min instances: 0, Max: 2             |
|                                          |
|  +-- Cloud SQL (PostgreSQL 15)           |
|  |   Instance: querysafe-db (db-f1-micro)|
|  |   Database: querysafe                 |
|  |                                       |
|  +-- GCS FUSE (/data mount)             |
|  |   Bucket: querysafe-v2-data           |
|  |   Documents, FAISS indexes, media     |
|  |                                       |
|  +-- Vertex AI (Gemini 2.0 Flash)       |
|      Chat + Vision processing            |
+------------------------------------------+
```

---

## Prerequisites

- Google Cloud SDK (`gcloud`) installed and authenticated
- Project: `querysafe-dev`
- Region: `asia-south1`
- Cloud SQL Admin API enabled
- Artifact Registry API enabled

---

## GCP Resources

### Cloud SQL Instance

```bash
# Already created — db-f1-micro, PostgreSQL 15
gcloud sql instances describe querysafe-db --project querysafe-dev

# Database: querysafe
# User: querysafe
# Connection: /cloudsql/querysafe-dev:asia-south1:querysafe-db
```

### GCS Bucket (for file storage)

```bash
# Bucket: querysafe-v2-data
# Mounted at /data via GCS FUSE on Cloud Run
gsutil ls gs://querysafe-v2-data/
```

---

## Deployment Command

From the project root directory:

```bash
gcloud run deploy querysafe-v2 \
  --source . \
  --region asia-south1 \
  --project querysafe-dev \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 2 \
  --timeout 300 \
  --add-cloudsql-instances querysafe-dev:asia-south1:querysafe-db \
  --update-env-vars ENVIRONMENT=production \
  --cpu-boost
```

This command:
1. Uploads source code (respects `.gcloudignore`)
2. Builds Docker image using `Dockerfile` in Cloud Build
3. Pushes image to Artifact Registry
4. Creates a new Cloud Run revision
5. Routes 100% traffic to the new revision

---

## Environment Variables

Set via Cloud Run console or `--update-env-vars`:

| Variable | Value | Notes |
|----------|-------|-------|
| `ENVIRONMENT` | `production` | Switches DB to PostgreSQL |
| `DB_NAME` | `querysafe` | Cloud SQL database name |
| `DB_USER` | `querysafe` | Cloud SQL user |
| `DB_PASSWORD` | *(secret)* | Cloud SQL password |
| `DB_HOST` | `/cloudsql/querysafe-dev:asia-south1:querysafe-db` | Cloud SQL socket |
| `DB_PORT` | `5432` | PostgreSQL port |
| `PROJECT_ID` | `querysafe-dev` | GCP project for Vertex AI |
| `REGION` | `asia-south1` | GCP region for Vertex AI |
| `SECRET_KEY` | *(secret)* | Django secret key |
| `WEBSITE_URL` | `https://console2.querysafe.ai` | Base URL for widget scripts |
| `ALLOWED_HOSTS` | `127.0.0.1,localhost,.run.app,.querysafe.ai` | Django allowed hosts |
| `CSRF_TRUSTED_ORIGINS` | `https://*.run.app,https://*.querysafe.ai` | CSRF trusted origins |

Email, Razorpay, and other secrets are set via `env.yaml` (excluded from deploy via `.gcloudignore`).

---

## Dockerfile

The Dockerfile:
1. Uses `python:3.13-slim` base
2. Installs system deps: `poppler-utils`, `libxml2-dev`, `libxslt1-dev`, `libpq-dev`
3. Installs PyTorch CPU-only (smaller image, no CUDA)
4. Installs Python dependencies from `requirements.txt`
5. **Pre-downloads SentenceTransformer model** (~90MB) into the image
6. Collects static files
7. On startup: runs `migrate` then starts Gunicorn (2 workers, 300s timeout)

---

## Database Management

### Local Development (SQLite)

```bash
# Local dev uses SQLite automatically (ENVIRONMENT != "production")
python manage.py runserver
```

### Production (PostgreSQL)

```bash
# Migrations run automatically on container startup (CMD in Dockerfile)

# To create an admin user on Cloud Run:
gcloud run jobs create create-admin \
  --image <LATEST_IMAGE_URL> \
  --command python \
  --args manage.py,createsuperuser,--noinput,--username,admin,--email,your@email.com \
  --region asia-south1 \
  --project querysafe-dev \
  --set-cloudsql-instances querysafe-dev:asia-south1:querysafe-db \
  --set-env-vars ENVIRONMENT=production,DB_NAME=querysafe,DB_USER=querysafe,DB_PASSWORD=<PASSWORD>,DB_HOST=/cloudsql/querysafe-dev:asia-south1:querysafe-db,DB_PORT=5432,PROJECT_ID=querysafe-dev,REGION=asia-south1,DJANGO_SUPERUSER_PASSWORD=<PASSWORD> \
  --memory 512Mi --cpu 1 --max-retries 0

gcloud run jobs execute create-admin --region asia-south1 --project querysafe-dev --wait
```

### Custom Management Command (QuerySafe user)

```bash
# Create a QuerySafe app user (not Django admin):
gcloud run jobs update create-admin \
  --args manage.py,create_admin,--name,Your Name,--email,your@email.com,--password,YourPassword \
  --region asia-south1 --project querysafe-dev

gcloud run jobs execute create-admin --region asia-south1 --project querysafe-dev --wait
```

---

## Custom Domain Setup

To map `console2.querysafe.ai` to Cloud Run:

```bash
# 1. Map the domain
gcloud run domain-mappings create \
  --service querysafe-v2 \
  --domain console2.querysafe.ai \
  --region asia-south1 \
  --project querysafe-dev

# 2. Get the DNS records to add
gcloud run domain-mappings describe \
  --domain console2.querysafe.ai \
  --region asia-south1 \
  --project querysafe-dev

# 3. Add CNAME record in your DNS provider:
#    console2.querysafe.ai → ghs.googlehosted.com
```

Update `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` in settings to include `.querysafe.ai`.

---

## Monitoring & Logs

```bash
# View recent logs
gcloud run services logs read querysafe-v2 --region asia-south1 --project querysafe-dev --limit 50

# View specific revision logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=querysafe-v2" \
  --project querysafe-dev --limit 20

# View Cloud Run job logs (admin creation, etc.)
gcloud logging read "resource.type=cloud_run_job" --project querysafe-dev --limit 20
```

---

## Key Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Container build instructions |
| `.gcloudignore` | Files excluded from deploy upload |
| `.dockerignore` | Files excluded from Docker context |
| `env.yaml` | Environment variables reference (NOT deployed) |
| `requirements.txt` | Python dependencies |
| `querySafe/settings.py` | Django settings (conditional DB config) |

---

## Current Deployment

| Property | Value |
|----------|-------|
| **Service** | `querysafe-v2` |
| **Region** | `asia-south1` |
| **URL** | `https://querysafe-v2-371440857764.asia-south1.run.app` |
| **Custom Domain** | `console2.querysafe.ai` (pending DNS setup) |
| **Latest Revision** | `querysafe-v2-00008-hxz` |
| **Cloud SQL** | `querysafe-dev:asia-south1:querysafe-db` (db-f1-micro) |
| **GCS Bucket** | `querysafe-v2-data` (mounted at `/data`) |
| **Memory** | 1Gi |
| **CPU** | 1 |
| **Workers** | 2 Gunicorn workers |
| **Timeout** | 300 seconds |
