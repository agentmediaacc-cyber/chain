# Use Python 3.12 slim for a smaller footprint
FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Install system dependencies
# - libpq-dev and gcc: for psycopg2
# - libmagic1: for python-magic
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    libmagic1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Ensure static/uploads exists (though it should be empty/ignored)
RUN mkdir -p static/uploads/profile/avatars static/uploads/profile/covers static/uploads/posts static/uploads/reels static/uploads/stories

# Expose the default Cloud Run port
EXPOSE 8080

# Run gunicorn
# - Using gevent as requested by the monkey patch in app.py
# - Binding to 0.0.0.0:$PORT
# - 4 workers (adjustable)
# - 120s timeout for longer calls/uploads
CMD gunicorn --bind 0.0.0.0:$PORT \
             --workers 4 \
             --worker-class gevent \
             --timeout 120 \
             "app:app"
