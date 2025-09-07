# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ===== Builder =====
FROM base AS builder

RUN apt-get update && apt-get install -y build-essential gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --prefix=/install -r requirements.txt

COPY app ./app
RUN mkdir -p /data && python app/data/generate_synthetic.py --rows 5000 --out /data/customers.csv

# ===== Final image =====
FROM base

COPY --from=builder /install /usr/local
COPY --from=builder /app /app
COPY --from=builder /data /data

EXPOSE 5000
CMD ["python", "app/main.py"]
