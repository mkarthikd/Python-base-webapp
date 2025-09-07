# syntax=docker/dockerfile:1

# ===== Base image =====
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ===== Builder stage =====
FROM base AS builder

# Install build dependencies only (including g++ for scikit-learn)
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Upgrade pip and install dependencies with wheels if possible
RUN python -m pip install --upgrade pip \
    && pip install --prefix=/install -r requirements.txt --prefer-binary

# Copy app code
COPY app ./app
COPY app/main.py ./main.py
COPY app/static ./static

# Generate synthetic data for CI/first run
# Add /install/lib/python3.11/site-packages to PYTHONPATH temporarily
ENV PYTHONPATH=/install/lib/python3.11/site-packages
RUN mkdir -p /data \
    && python app/data/generate_synthetic.py --rows 5000 --out /data/customers.csv

# ===== Final stage =====
FROM base

# Copy installed packages from builder
COPY --from=builder /install /usr/local
COPY --from=builder /app /app
COPY --from=builder /data /data

EXPOSE 5000
CMD ["python", "main.py"]