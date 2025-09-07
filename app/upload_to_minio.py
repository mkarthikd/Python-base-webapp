import os
import pandas as pd
import boto3
from datetime import datetime
import numpy as np

# MinIO connection
endpoint = os.getenv("MINIO_ENDPOINT", "http://minio.data-lake.svc.cluster.local:9000")
access_key = os.getenv("MINIO_ACCESS_KEY")
secret_key = os.getenv("MINIO_SECRET_KEY")
bucket_name = os.getenv("MINIO_BUCKET", "telecom-data")

# Generate synthetic data
rows = 1000
df = pd.DataFrame({
    "customer_id": range(1, rows + 1),
    "plan": np.random.choice(["prepaid", "postpaid"], size=rows),
    "usage_minutes": np.random.randint(50, 500, size=rows),
    "charges": np.random.uniform(10, 100, size=rows).round(2),
    "created_at": datetime.now().isoformat()
})

filename = f"customers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
df.to_csv(filename, index=False)

# Upload to MinIO
s3 = boto3.client(
    "s3",
    endpoint_url=endpoint,
    aws_access_key_id=access_key,
    aws_secret_access_key=secret_key,
)

s3.upload_file(filename, bucket_name, filename)

print(f"✅ Uploaded {filename} to bucket {bucket_name}")
