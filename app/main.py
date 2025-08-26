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
_customers_cache = pd.read_csv(DATA_PATH) if os.path.exists(DATA_PATH) else pd.DataFrame()


def load_data():
    global _customers_cache
    if _customers_cache is None or _customers_cache.empty:
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


def apply_filters_sort_limit(df, results, default_sort="customer_id", default_order="asc"):
    """
    Apply region filter, sorting, and limit based on query params.
    """
    # Optional region filter
    region_filter = request.args.get("region")
    if region_filter:
        df = df[df["region"].str.lower() == region_filter.lower()]
        results = [r for r in results if r.get("region", "").lower() == region_filter.lower()]

    # Sorting params
    sort_col = request.args.get("sort", default_sort)
    sort_order = request.args.get("order", default_order)

    if results and sort_col in results[0]:
        results = sorted(
            results,
            key=lambda x: x[sort_col],
            reverse=(sort_order.lower() == "desc")
        )

    # Limit param
    try:
        limit = int(request.args.get("limit", 10))
    except:
        limit = 10

    return results[:limit], len(results)


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
                "name": row["name"],
                "region": row["region"],
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
                "name": row["name"],
                "region": row["region"],
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
    total_savings_amount = float(df.loc[savings_mask, "savings"].sum())
    total_upsell_amount = float(-df.loc[upsell_mask, "savings"].sum())

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
        },
        "sample": results  # shows top N rows after sort/filter
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
