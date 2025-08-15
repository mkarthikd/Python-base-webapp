# Simple rule-based recommender (placeholder for ML model)
PLAN_CATALOG = [
    {"name": "Basic", "data_gb": 10, "minutes": 200, "sms": 100, "price": 199},
    {"name": "Standard", "data_gb": 50, "minutes": 1000, "sms": 500, "price": 499},
    {"name": "Premium", "data_gb": 200, "minutes": 3000, "sms": 2000, "price": 999},
]

def recommend_plan(customer: dict):
    data = float(customer.get("avg_monthly_data_gb", 0))
    mins = float(customer.get("avg_monthly_minutes", 0))
    sms  = float(customer.get("avg_monthly_sms", 0))
    spend = float(customer.get("avg_monthly_spend", 0))

    # Plan selection rules
    if data < 8 and mins < 300 and sms < 150:
        plan = PLAN_CATALOG[0]
    elif data < 80 and mins < 1500 and sms < 1000:
        plan = PLAN_CATALOG[1]
    else:
        plan = PLAN_CATALOG[2]

    # Calculate savings (positive means cheaper plan suggested)
    savings = spend - plan["price"]

    # Customer-friendly explanation
    if savings > 0:
        reason_text = "to save money"
    else:
        reason_text = "for better data benefits and to avoid extra charges"

    recommendation_reason = (
        f"Customer currently spends ₹{spend:.0f}/month. "
        f"Based on their usage ({data}GB data, {mins} mins calls, {sms} SMS), "
        f"the {plan['name']} plan at ₹{plan['price']} is recommended {reason_text}."
    )

    return {
        "customer_id": int(customer.get("customer_id", -1)),
        "recommended_plan": plan["name"],
        "estimated_monthly_bill": plan["price"],
        "estimated_savings": round(savings, 2),
        "recommendation_reason": recommendation_reason
    }
