from flask import Flask, jsonify, request, send_from_directory
import os
import pandas as pd

from app.model.recommender import recommend_plan, PLAN_CATALOG

# Read secret from environment (will come from K8s Secret)
app_secret = os.environ.get("APP_SECRET", "default_secret")

app = Flask(__name__)
# Use the secret as Flask's built-in SECRET_KEY (for sessions, CSRF, etc.)
app.config["SECRET_KEY"] = app_secret


@app.route("/")
def dashboard():
    return send_from_directory("static", "index.html")


DATA_PATH = os.environ.get("CUSTOMER_DATA", "app/data/customers.csv")
_customers_cache = None

def load_data():
    global _customers_cache
    if _customers_cache is None:
        if os.path.exists(DATA_PATH):
            df = pd.read_csv(DATA_PATH)
            # Ensure required columns exist, even if missing in CSV
            for col in ["name", "region"]:
                if col not in df.columns:
                    df[col] = ""
            _customers_cache = df
        else:
            _customers_cache = pd.DataFrame(columns=[
                "customer_id", "name", "region",
                "avg_monthly_data_gb", "avg_monthly_minutes",
                "avg_monthly_sms", "avg_monthly_spend"
            ])
    return _customers_cache


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/customers")
def customers():
    df = load_data()
    if df.empty:
        return jsonify(customers=[], total=0)
    try:
        limit = int(request.args.get("limit", 100))
    except:
        limit = 100

    sample = df.sample(min(limit, len(df)), random_state=42)

    output = sample[[
        "customer_id", "name", "region",
        "avg_monthly_data_gb", "avg_monthly_minutes",
        "avg_monthly_sms", "avg_monthly_spend"
    ]].to_dict(orient="records")

    return jsonify(customers=output, total=int(len(df)))


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

    region_filter = request.args.get("region")
    if region_filter:
        df = df[df["region"].str.lower() == region_filter.lower()]

    results = []
    for _, row in df.iterrows():
        rec = recommend_plan(row.to_dict())
        savings = rec.get("estimated_savings", 0)
        if savings > 0:
            results.append({
                "customer_id": row["customer_id"],
                "name": row["name"],
                "region": row["region"],
                **rec
            })

    results = sorted(results, key=lambda x: x["estimated_savings"], reverse=True)

    try:
        limit = int(request.args.get("limit", 10))
    except:
        limit = 10

    return jsonify(top_savings=results[:limit], total=len(results))


@app.get("/top_upsell")
def top_upsell():
    df = load_data()
    if df.empty:
        return jsonify(error="No data loaded"), 404

    region_filter = request.args.get("region")
    if region_filter:
        df = df[df["region"].str.lower() == region_filter.lower()]

    results = []
    for _, row in df.iterrows():
        rec = recommend_plan(row.to_dict())
        savings = rec.get("estimated_savings", 0)
        if savings < 0:
            results.append({
                "customer_id": row["customer_id"],
                "name": row["name"],
                "region": row["region"],
                **rec
            })

    results = sorted(results, key=lambda x: x["estimated_savings"])  # Most negative first

    try:
        limit = int(request.args.get("limit", 10))
    except:
        limit = 10

    return jsonify(top_upsell=results[:limit], total=len(results))


@app.get("/summary_stats")
def summary_stats():
    df = load_data()
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

    savings_count = 0
    upsell_count = 0
    total_savings_amount = 0
    total_upsell_amount = 0

    for _, row in df.iterrows():
        rec = recommend_plan(row.to_dict())
        savings = rec.get("estimated_savings", 0)
        if savings > 0:
            savings_count += 1
            total_savings_amount += savings
        elif savings < 0:
            upsell_count += 1
            total_upsell_amount += abs(savings)

    return jsonify({
        "region": region_filter if region_filter else "All",
        "total_customers": total_customers,
        "avg_monthly_spend": round(avg_spend, 2),
        "total_current_spend": round(total_spend, 2),
        "savings_opportunities": {
            "count": savings_count,
            "total_potential_savings": round(total_savings_amount, 2)
        },
        "upsell_opportunities": {
            "count": upsell_count,
            "total_potential_revenue": round(total_upsell_amount, 2)
        }
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
