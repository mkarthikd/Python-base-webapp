# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app ./app
COPY app/main.py ./main.py

# Copy customers.csv into image at /data
COPY app/data/customers.csv /data/customers.csv

EXPOSE 5000

CMD ["python", "main.py"]
