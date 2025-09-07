from flask import Flask, jsonify, request, send_from_directory
import os
import pandas as pd
import traceback
from minio import Minio
from minio.error import S3Error

from app.model.recommender import recommend_plan, PLAN_CATALOG

# Read secret from environment (will come from K8s Secret)
app_secret = os.environ.get("APP_SECRET", "default_secret")

app = Flask(__name__)
# Use the secret as Flask's built-in SECRET_KEY (for sessions, CSRF, etc.)
app.config["SECRET_KEY"] = app_secret

# Environment / MinIO config
CUSTOMER_DATA = os.environ.get("CUSTOMER_DATA", "app/data/customers.csv")  # can be local path
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "telecom-data")
CUSTOMER_DATA_OBJECT = os.environ.get("CUSTOMER_DATA_OBJECT", "customers.csv")
_TEMP_DOWNLOAD_PATH = "/tmp/customers.csv"

# In-memory cache for customers dataframe
_customers_cache = None


def get_minio_client():
    """
    Create and return a Minio client if credentials are available, otherwise None.
    Accepts MINIO_ENDPOINT with or without scheme.
    """
    if not MINIO_ENDPOINT or not MINIO_ACCESS_KEY or not MINIO_SECRET_KEY:
        print("MinIO credentials or endpoint missing - will not attempt MinIO access.")
        return None

    endpoint = MINIO_ENDPOINT.strip()
    # strip scheme if present; Minio client expects host:port or host
    if endpoint.startswith("http://"):
        endpoint = endpoint[len("http://"):]
    elif endpoint.startswith("https://"):
        endpoint = endpoint[len("https://"):]

    # Remove trailing slashes
    endpoint = endpoint.rstrip("/")

    secure = MINIO_ENDPOINT.startswith("https://") if MINIO_ENDPOINT else False

    try:
        client = Minio(
            endpoint,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=secure
        )
        return client
    except Exception as e:
        print("Failed to create MinIO client:", e)
        return None


def download_customer_data_from_minio(minio_client) -> str:
    """
    Attempt to download CUSTOMER_DATA_OBJECT from MINIO_BUCKET to a temp path.
    Returns path to downloaded file or raises exception.
    """
    if not minio_client:
        raise RuntimeError("MinIO client is not available")

    # Ensure bucket exists
    try:
        found = minio_client.bucket_exists(MINIO_BUCKET)
        if not found:
            raise RuntimeError(f"Bucket '{MINIO_BUCKET}' does not exist.")
    except S3Error as e:
        raise RuntimeError(f"Error checking bucket existence: {e}")

    dest_path = _TEMP_DOWNLOAD_PATH
    try:
        print(f"Downloading object '{CUSTOMER_DATA_OBJECT}' from bucket '{MINIO_BUCKET}' to '{dest_path}'...")
        minio_client.fget_object(MINIO_BUCKET, CUSTOMER_DATA_OBJECT, dest_path)
        if os.path.exists(dest_path):
            print("Download complete:", dest_path)
            return dest_path
        else:
            raise RuntimeError("Download reported success but file not found on disk.")
    except Exception as e:
        raise RuntimeError(f"Failed to download object from MinIO: {e}")


def ensure_customer_data_available() -> str:
    """
    Ensure there's a CSV to load. Returns a local filesystem path to the CSV.
    Priority:
      1. CUSTOMER_DATA if exists on disk
      2. Attempt download from MinIO (if configured)
      3. Raise if nothing available
    """
    # If CUSTOMER_DATA points to a local path that exists, use it
    if os.path.exists(CUSTOMER_DATA):
        print(f"Using local CUSTOMER_DATA at {CUSTOMER_DATA}")
        return CUSTOMER_DATA

    # Try to download from MinIO if credentials present
    minio_client = get_minio_client()
    if minio_client:
        try:
            downloaded = download_customer_data_from_minio(minio_client)
            return downloaded
        except Exception as e:
            print("MinIO download attempt failed:", e)
            print(traceback.format_exc())

    # Nothing available
    raise FileNotFoundError(f"Customer data not found locally at '{CUSTOMER_DATA}' and MinIO download failed or not configured.")


def load_data():
    """
    Load the customer CSV into a pandas DataFrame (cached).
    If no CSV is available, returns an empty DataFrame with expected columns.
    """
    global _customers_cache
    if _customers_cache is not None and not _customers_cache.empty:
        return _customers_cache

    try:
        csv_path = ensure_customer_data_available()
        df = pd.read_csv(csv_path)
        # Ensure required columns exist, even if missing in CSV
        for col in ["customer_id", "name", "region", "avg_monthly_data_gb",
                    "avg_monthly_minutes", "avg_monthly_sms", "avg_monthly_spend"]:
            if col not in df.columns:
                df[col] = "" if col in ["name", "region"] else 0
        # Cast customer_id to int if possible
        try:
            df["customer_id"] = df["customer_id"].astype(int)
        except Exception:
            # leave as-is if conversion fails
            pass

        _customers_cache = df
        print(f"Loaded customer data from {csv_path} ({len(df)} rows).")
    except FileNotFoundError as e:
        print("No customer data available:", e)
        _customers_cache = pd.DataFrame(columns=[
            "customer_id", "name", "region",
            "avg_monthly_data_gb", "avg_monthly_minutes",
            "avg_monthly_sms", "avg_monthly_spend"
        ])
    except Exception as e:
        print("Unexpected error loading data:", e)
        print(traceback.format_exc())
        _customers_cache = pd.DataFrame(columns=[
            "customer_id", "name", "region",
            "avg_monthly_data_gb", "avg_monthly_minutes",
            "avg_monthly_sms", "avg_monthly_spend"
        ])
    return _customers_cache


def apply_filters_sort_limit(df, results, default_sort="customer_id", default_order="asc"):
    """
    Apply region filter, sorting, and limit based on query params.
    """
    # Optional region filter
    region_filter = request.args.get("region")
    if region_filter and not df.empty:
        df = df[df["region"].str.lower() == region_filter.lower()]
        results = [r for r in results if r.get("region", "").lower() == region_filter.lower()]

    # Sorting params
    sort_col = request.args.get("sort", default_sort)
    sort_order = request.args.get("order", default_order)

    if results and sort_col in results[0]:
        results = sorted(
            results,
            key=lambda x: x.get(sort_col, 0),
            reverse=(sort_order.lower() == "desc")
        )

    # Limit param
    try:
        limit = int(request.args.get("limit", 10))
    except:
        limit = 10

    return results[:limit], len(results)


@app.route("/")
def dashboard():
    return send_from_directory("static", "index.html")


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/customers")
def customers():
    df = load_data()
    if df.empty:
        return jsonify(customers=[], total=0)

    results = df[[
        "customer_id", "name", "region",
        "avg_monthly_data_gb", "avg_monthly_minutes",
        "avg_monthly_sms", "avg_monthly_spend"
    ]].to_dict(orient="records")

    results, total = apply_filters_sort_limit(df, results, default_sort="customer_id")
    return jsonify(customers=results, total=total)


@app.get("/recommend/<int:customer_id>")
def recommend(customer_id: int):
    df = load_data()
    if df.empty:
        return jsonify(error="No data loaded"), 404
    row = df[df['customer_id'] == customer_id]
    if row.empty:
        return jsonify(error="Customer not found"), 404
    rec = recommend_plan(row.iloc[0].to_dict())
    return jsonify(rec)


@app.get("/top_savings")
def top_savings():
    df = load_data()
    if df.empty:
        return jsonify(error="No data loaded"), 404

    results = []
    for _, row in df.iterrows():
        rec = recommend_plan(row.to_dict())
        if rec.get("estimated_savings", 0) > 0:
            results.append({
                "customer_id": row["customer_id"],
                "name": row.get("name", ""),
                "region": row.get("region", ""),
                **rec
            })

    results, total = apply_filters_sort_limit(df, results, default_sort="estimated_savings", default_order="desc")
    return jsonify(top_savings=results, total=total)


@app.get("/top_upsell")
def top_upsell():
    df = load_data()
    if df.empty:
        return jsonify(error="No data loaded"), 404

    results = []
    for _, row in df.iterrows():
        rec = recommend_plan(row.to_dict())
        if rec.get("estimated_savings", 0) < 0:
            results.append({
                "customer_id": row["customer_id"],
                "name": row.get("name", ""),
                "region": row.get("region", ""),
                **rec
            })

    results, total = apply_filters_sort_limit(df, results, default_sort="estimated_savings", default_order="asc")
    return jsonify(top_upsell=results, total=total)


@app.get("/summary_stats")
def summary_stats():
    df = load_data()
    if df.empty:
        return jsonify(error="No data loaded"), 404

    # Apply region filter before stats
    region_filter = request.args.get("region")
    if region_filter:
        df = df[df["region"].str.lower() == region_filter.lower()]

    if df.empty:
        return jsonify(error=f"No data found for region '{region_filter}'"), 404

    total_customers = len(df)
    total_spend = df["avg_monthly_spend"].sum()
    avg_spend = df["avg_monthly_spend"].mean()

    # Recommendations for all
    df["rec"] = df.apply(lambda row: recommend_plan(row.to_dict()), axis=1)
    df["savings"] = df["rec"].apply(lambda r: r.get("estimated_savings", 0))

    # Prepare base results
    results = df.to_dict(orient="records")

    # Reuse helper for sorting/limit
    results, total = apply_filters_sort_limit(df, results, default_sort="savings", default_order="desc")

    # Aggregate stats
    savings_mask = df["savings"] > 0
    upsell_mask = df["savings"] < 0

    savings_count = int(savings_mask.sum())
    upsell_count = int(upsell_mask.sum())
    total_savings_amount = float(df.loc[savings_mask, "savings"].sum()) if savings_count > 0 else 0.0
    total_upsell_amount = float(-df.loc[upsell_mask, "savings"].sum()) if upsell_count > 0 else 0.0

    return jsonify({
        "region": region_filter if region_filter else "All",
        "total_customers": total_customers,
        "avg_monthly_spend": round(avg_spend, 2) if not pd.isna(avg_spend) else 0.0,
        "total_current_spend": round(total_spend, 2),
        "savings_opportunities": {
            "count": savings_count,
            "total_potential_savings": round(total_savings_amount, 2)
        },
        "upsell_opportunities": {
            "count": upsell_count,
            "total_potential_revenue": round(total_upsell_amount, 2)
        },
        "sample": results  # shows top N rows after sort/filter
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # Do a first load attempt so readiness checks are meaningful
    try:
        load_data()
    except Exception as e:
        print("Initial load_data() failed:", e)
    app.run(host="0.0.0.0", port=port)
