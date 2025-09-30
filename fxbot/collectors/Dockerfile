FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY collectors/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY collectors/ ./collectors/
COPY core/ ./core/
COPY infrastructure/ ./infrastructure/

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

WORKDIR /app/collectors
CMD ["python", "main.py"]