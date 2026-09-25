FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        build-essential \
        libpq-dev \
        libffi-dev \
        libssl-dev \
        libjpeg-dev \
        libpng-dev \
        libwebp-dev \
        libxml2-dev \
        libxslt-dev \
        libpango1.0-dev \
        libcairo2-dev \
        libgdk-pixbuf2.0-dev \
        shared-mime-info \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Create necessary directories
RUN mkdir -p /app/staticfiles /app/media /app/logs

# Create a non-root user
RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app \
    && mkdir -p /app/beat-schedule && chown -R appuser:appuser /app/beat-schedule \
    && chmod +x /app/entrypoint.sh

USER appuser

# Expose port
EXPOSE 8000

# Entrypoint waits for DB/Redis, collects static, then runs CMD.
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "adom.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--max-requests", "1000", "--max-requests-jitter", "100", "--timeout", "120", "--access-logfile", "-"]