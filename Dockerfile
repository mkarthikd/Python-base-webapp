# syntax=docker/dockerfile:1

# ===== Builder stage =====
FROM python:3.11-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_CACHE_DIR=/root/.cache/pip

WORKDIR /app

# 1. Copy only requirements first to leverage Docker cache
COPY requirements.txt ./

# 2. Install Python dependencies (cacheable layer)
RUN python -m pip install --upgrade pip && \
    pip install --cache-dir=$PIP_CACHE_DIR -r requirements.txt

# 3. Copy application code
COPY app ./app
COPY app/main.py ./main.py
COPY app/static ./static

# 4. Generate synthetic data (optional for CI)
RUN mkdir -p /data && \
    python app/data/generate_synthetic.py --rows 5000 --out /data/customers.csv

# ===== Final stage =====
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 5. Copy dependencies and app from builder
COPY --from=builder /root/.cache/pip /root/.cache/pip
COPY --from=builder /app /app
COPY --from=builder /data /data

# 6. Expose port for Flask
EXPOSE 5000

# 7. Start app
CMD ["python", "main.py"]
