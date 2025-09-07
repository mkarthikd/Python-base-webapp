# syntax=docker/dockerfile:1

# ===== Base Image =====
FROM python:3.11-alpine AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# ===== Builder Stage =====
FROM base AS builder

# Install build dependencies
RUN apk add --no-cache gcc musl-dev gfortran

# Copy requirements first to leverage caching
COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --prefix=/install -r requirements.txt

# Copy app code
COPY app ./app
COPY app/main.py ./main.py
COPY app/static ./static

# Generate synthetic customer data
RUN mkdir -p /data && \
    python app/data/generate_synthetic.py --rows 5000 --out /data/customers.csv

# ===== Final Image =====
FROM base

# Copy installed packages from builder
COPY --from=builder /install /usr/local
COPY --from=builder /app /app
COPY --from=builder /data /data

EXPOSE 5000

CMD ["python", "main.py"]
