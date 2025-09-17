from flask import Flask, jsonify, request, send_from_directory
import os
import pandas as pd
import traceback
from sqlalchemy import create_engine, text

from app.model.recommender import recommend_plan, PLAN_CATALOG

# ------------------ Configuration ------------------
app_secret = os.environ.get("APP_SECRET", "default_secret")
POSTGRES_URL = os.environ.get(
    "POSTGRES_URL",
    "postgresql+asyncpg://iceberg:icebergpass@postgres-rw.data-lake.svc.cluster.local:5432/iceberg"
)

app = Flask(__name__)
app.config["SECRET_KEY"] = app_secret

# ------------------ Database Functions ------------------
def get_engine():
    return create_engine(POSTGRES_URL)

def load_customers_from_db():
    """
    Load customers from PostgreSQL into a pandas DataFrame.
    """
    try:
        engine = get_engine()
        query = "SELECT * FROM customers"
        df = pd.read_sql(query, engine)
        if df.empty:
            print("No customer data found in DB.")
        return df
    except Exception as e:
        print("Error loading customers from PostgreSQL:", e)
        print(traceback.format_exc())
        return pd.DataFrame(columns=[
            "customer_id", "name", "region",
            "avg_monthly_data_gb", "avg_monthly_minutes",
            "avg_monthly_sms", "avg_monthly_spend"
        ])

def apply_filters_sort_limit(df, results, default_sort="customer_id", default_order="asc"):
    region_filter = request.args.get("region")
    if region_filter and not df.empty:
        df = df[df["region"].str.lower() == region_filter.lower()]
        results = [r for r in results if r.get("region", "").lower() == region_filter.lower()]

    sort_col = request.args.get("sort", default_sort)
    sort_order = request.args.get("order", default_order)

    if results and sort_col in results[0]:
        results = sorted(
            results,
            key=lambda x: x.get(sort_col, 0),
            reverse=(sort_order.lower() == "desc")
        )

    try:
        limit = int(request.args.get("limit", 10))
    except:
        limit = 10

    return results[:limit], len(results)

# ------------------ API Routes ------------------
@app.route("/")
def dashboard():
    return send_from_directory("static", "index.html")

@app.get("/health")
def health():
    return jsonify(status="ok")

@app.get("/customers")
def customers():
    df = load_customers_from_db()
    if df.empty:
        return jsonify(customers=[], total=0)

    results = df.to_dict(orient="records")
    results, total = apply_filters_sort_limit(df, results)
    return jsonify(customers=results, total=total)

@app.get("/recommend/<int:customer_id>")
def recommend(customer_id: int):
    df = load_customers_from_db()
    if df.empty:
        return jsonify(error="No data loaded"), 404
    row = df[df['customer_id'] == customer_id]
    if row.empty:
        return jsonify(error="Customer not found"), 404
    rec = recommend_plan(row.iloc[0].to_dict())
    return jsonify(rec)

@app.get("/top_savings")
def top_savings():
    df = load_customers_from_db()
    if df.empty:
        return jsonify(error="No data loaded"), 404

    results = []
    for _, row in df.iterrows():
        rec = recommend_plan(row.to_dict())
        if rec.get("estimated_savings", 0) > 0:
            results.append({**row.to_dict(), **rec})

    results, total = apply_filters_sort_limit(df, results, default_sort="estimated_savings", default_order="desc")
    return jsonify(top_savings=results, total=total)

@app.get("/top_upsell")
def top_upsell():
    df = load_customers_from_db()
    if df.empty:
        return jsonify(error="No data loaded"), 404

    results = []
    for _, row in df.iterrows():
        rec = recommend_plan(row.to_dict())
        if rec.get("estimated_savings", 0) < 0:
            results.append({**row.to_dict(), **rec})

    results, total = apply_filters_sort_limit(df, results, default_sort="estimated_savings", default_order="asc")
    return jsonify(top_upsell=results, total=total)

@app.get("/summary_stats")
def summary_stats():
    df = load_customers_from_db()
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

    results = df.to_dict(orient="records")
    results, total = apply_filters_sort_limit(df, results, default_sort="savings", default_order="desc")

    savings_mask = df["savings"] > 0
    upsell_mask = df["savings"] < 0

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
    app.run(host="0.0.0.0", port=port)
