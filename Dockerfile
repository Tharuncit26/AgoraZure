FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Seed initial database with demo shops and data
RUN python seed.py

# Expose default port
ENV PORT=8000
EXPOSE 8000

# Run uvicorn on dynamically assigned port
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}
