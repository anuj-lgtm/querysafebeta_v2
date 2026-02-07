FROM python:3.13-slim

WORKDIR /app

# Install system dependencies for pdf2image, lxml, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    libxml2-dev \
    libxslt1-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch CPU-only FIRST (before requirements.txt)
RUN pip install --no-cache-dir torch==2.7.0 --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Pre-download SentenceTransformer model into the image (~90MB)
# This avoids a slow download on first request in Cloud Run
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Collect static files at build time
RUN python manage.py collectstatic --noinput 2>/dev/null || true

EXPOSE 8080

CMD ["sh", "-c", "python manage.py migrate && gunicorn querySafe.wsgi:application --bind 0.0.0.0:${PORT:-8080} --workers 2 --timeout 300"]
