# Use Python 3.12 to match local dev
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates procps \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first for layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . /app

# Ensure launcher is executable
RUN chmod +x /app/run_local.sh

# Expose Chainlit port
EXPOSE 8500

# Default command: start MCP/Vendor + Chainlit
CMD ["/bin/bash", "-lc", "./run_local.sh"]
