# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY app/main.py ./main.py
COPY app/static ./static

# Generate synthetic customers.csv into /data at build time
RUN mkdir -p /data && \
    python app/data/generate_synthetic.py --rows 5000 --out /data/customers.csv

# Flask app runs on 5000
EXPOSE 5000

CMD ["python", "main.py"]
