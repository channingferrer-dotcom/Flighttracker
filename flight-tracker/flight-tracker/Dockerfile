FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8080

# Use shell form so $PORT is expanded at runtime by Railway
CMD gunicorn app:app --workers 1 --threads 2 --timeout 120 --bind 0.0.0.0:${PORT:-8080}
