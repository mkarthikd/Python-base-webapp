# syntax=docker/dockerfile:1

FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ===== Builder =====
FROM base AS builder

# Install build deps only here (not in final image)
RUN apt-get update && apt-get install -y build-essential gcc && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install --prefix=/install -r requirements.txt

# Copy app code
COPY app ./app
COPY app/main.py ./main.py
COPY app/static ./static

RUN mkdir -p /data && \
    python app/data/generate_synthetic.py --rows 5000 --out /data/customers.csv

# ===== Final image =====
FROM base

# Copy installed packages without pip cache
COPY --from=builder /install /usr/local
COPY --from=builder /app /app
COPY --from=builder /data /data

EXPOSE 5000
CMD ["python", "main.py"]
