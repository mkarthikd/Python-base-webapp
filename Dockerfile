# syntax=docker/dockerfile:1

# ===== Builder =====
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_CACHE_DIR=/root/.cache/pip

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .

# Install dependencies
RUN python -m pip install --upgrade pip && \
    pip install --cache-dir=$PIP_CACHE_DIR -r requirements.txt

# Copy app code
COPY app ./app
COPY app/main.py ./main.py
COPY app/static ./static

# Optional: generate synthetic data
RUN mkdir -p /data && \
    python app/data/generate_synthetic.py --rows 5000 --out /data/customers.csv

# ===== Final stage =====
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy app and data
COPY --from=builder /app /app
COPY --from=builder /data /data

EXPOSE 5000

CMD ["python", "main.py"]
