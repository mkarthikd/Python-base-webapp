from flask import Flask, jsonify, request, send_from_directory
import os
import pandas as pd
import traceback
from sqlalchemy import create_engine

from app.model.recommender import recommend_plan, PLAN_CATALOG

# ------------------ Configuration ------------------
app_secret = os.environ.get("APP_SECRET", "default_secret")
CUSTOMER_DATA = os.environ.get("CUSTOMER_DATA", "/data/customers.csv")
POSTGRES_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql+asyncpg://iceberg:icebergpass@postgres-rw.data-lake.svc.cluster.local:5432/iceberg"
)

app = Flask(__name__)
app.config["SECRET_KEY"] = app_secret

# ------------------ Database Functions ------------------
def get_engine():
    return create_engine(POSTGRES_URL)

def load_csv_to_postgres():
    """Load CSV data into PostgreSQL 'customers' table."""
    if not os.path.exists(CUSTOMER_DATA):
        print(f"{CUSTOMER_DATA} not found. Skipping DB load.")
        return

    try:
        df = pd.read_csv(CUSTOMER_DATA)
        engine = get_engine()
        df.to_sql("customers", engine, if_exists="replace", index=False)
        print(f"Loaded {len(df)} rows into PostgreSQL table 'customers'.")
    except Exception as e:
        print("Error loading CSV to PostgreSQL:", e)
        print(traceback.format_exc())

def query_customers(sql: str):
    """Run SQL query and return DataFrame"""
    try:
        engine = get_engine()
        return pd.read_sql(sql, engine)
    except Exception as e:
        print("Database query error:", e)
        print(traceback.format_exc())
        return pd.DataFrame()  # empty fallback

# ------------------ API Routes ------------------
@app.route("/")
def dashboard():
    return send_from_directory("static", "index.html")

@app.get("/health")
def health():
    return jsonify(status="ok")

@app.get("/customers")
def customers():
    df = query_customers("SELECT * FROM customers")
    if df.empty:
        return jsonify(customers=[], total=0)

    results = df.to_dict(orient="records")
    # Optional filters/sorting
    region_filter = request.args.get("region")
    if region_filter:
        results = [r for r in results if r.get("region", "").lower() == region_filter.lower()]
    sort_col = request.args.get("sort", "customer_id")
    sort_order = request.args.get("order", "asc")
    results = sorted(results, key=lambda x: x.get(sort_col, 0), reverse=(sort_order.lower() == "desc"))
    limit = int(request.args.get("limit", 10))
    return jsonify(customers=results[:limit], total=len(results))

@app.get("/recommend/<int:customer_id>")
def recommend(customer_id: int):
    df = query_customers(f"SELECT * FROM customers WHERE customer_id={customer_id}")
    if df.empty:
        return jsonify(error="Customer not found"), 404
    rec = recommend_plan(df.iloc[0].to_dict())
    return jsonify(rec)

@app.get("/top_savings")
def top_savings():
    df = query_customers("SELECT * FROM customers")
    if df.empty:
        return jsonify(error="No data loaded"), 404

    results = []
    for _, row in df.iterrows():
        rec = recommend_plan(row.to_dict())
        if rec.get("estimated_savings", 0) > 0:
            results.append({**row.to_dict(), **rec})

    results = sorted(results, key=lambda x: x.get("estimated_savings", 0), reverse=True)
    limit = int(request.args.get("limit", 10))
    return jsonify(top_savings=results[:limit], total=len(results))

@app.get("/top_upsell")
def top_upsell():
    df = query_customers("SELECT * FROM customers")
    if df.empty:
        return jsonify(error="No data loaded"), 404

    results = []
    for _, row in df.iterrows():
        rec = recommend_plan(row.to_dict())
        if rec.get("estimated_savings", 0) < 0:
            results.append({**row.to_dict(), **rec})

    results = sorted(results, key=lambda x: x.get("estimated_savings", 0))
    limit = int(request.args.get("limit", 10))
    return jsonify(top_upsell=results[:limit], total=len(results))

@app.get("/summary_stats")
def summary_stats():
    df = query_customers("SELECT * FROM customers")
    if df.empty:
        return jsonify(error="No data loaded"), 404

    region_filter = request.args.get("region")
    if region_filter:
        df = df[df["region"].str.lower() == region_filter.lower()]

    if df.empty:
        return jsonify(error=f"No data found for region '{region_filter}'"), 404

    total_customers = len(df)
    total_spend = df["avg_monthly_spend"].sum()
    avg_spend = df["avg_monthly_spend"].mean()

    df["rec"] = df.apply(lambda row: recommend_plan(row.to_dict()), axis=1)
    df["savings"] = df["rec"].apply(lambda r: r.get("estimated_savings", 0))

    savings_mask = df["savings"] > 0
    upsell_mask = df["savings"] < 0
    results = df.to_dict(orient="records")

    return jsonify({
        "region": region_filter if region_filter else "All",
        "total_customers": total_customers,
        "avg_monthly_spend": round(avg_spend, 2) if not pd.isna(avg_spend) else 0.0,
        "total_current_spend": round(total_spend, 2),
        "savings_opportunities": {
            "count": int(savings_mask.sum()),
            "total_potential_savings": round(float(df.loc[savings_mask, "savings"].sum()) if int(savings_mask.sum()) > 0 else 0.0, 2)
        },
        "upsell_opportunities": {
            "count": int(upsell_mask.sum()),
            "total_potential_revenue": round(float(-df.loc[upsell_mask, "savings"].sum()) if int(upsell_mask.sum()) > 0 else 0.0, 2)
        },
        "sample": results
    })

# ------------------ Run ------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    load_csv_to_postgres()  # CSV → PostgreSQL on startup
    app.run(host="0.0.0.0", port=port)
