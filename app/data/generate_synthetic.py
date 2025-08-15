import pandas as pd
import numpy as np
import random
import os
import argparse

# Argument parsing
parser = argparse.ArgumentParser(description="Generate synthetic customer data")
parser.add_argument("--rows", type=int, default=500, help="Number of customers to generate")
parser.add_argument("--out", type=str, default=os.environ.get("CUSTOMER_DATA", "app/data/customers.csv"), help="Output CSV file path")
args = parser.parse_args()

NUM_CUSTOMERS = args.rows
OUTPUT_PATH = args.out

# Region-specific first names
region_names = {
    "Delhi": ["Amit", "Priya", "Vikas", "Neha", "Anil", "Pooja", "Rajat", "Ritu"],
    "Mumbai": ["Rohit", "Kiran", "Sanjay", "Anita", "Deepak", "Meera", "Sunil", "Sneha"],
    "Bangalore": ["Karthik", "Ananya", "Ravi", "Divya", "Manoj", "Shreya", "Vikram", "Pavitra"],
    "Chennai": ["Arun", "Lakshmi", "Suresh", "Priya", "Ramesh", "Deepa", "Vijay", "Anitha"],
    "Kolkata": ["Sourav", "Moushumi", "Anirban", "Rupa", "Debasish", "Madhumita", "Subhas", "Sutapa"],
    "Hyderabad": ["Rajesh", "Swapna", "Srinivas", "Bhavana", "Praveen", "Lavanya", "Anil", "Padma"],
    "Pune": ["Ajay", "Smita", "Nitin", "Madhuri", "Rahul", "Pallavi", "Ashish", "Vidya"],
    "Ahmedabad": ["Hitesh", "Janki", "Paresh", "Hetal", "Mukesh", "Kinjal", "Sanjay", "Nisha"]
}

# Common Indian last names
last_names = ["Sharma", "Verma", "Kumar", "Patel", "Reddy", "Singh", "Nair", "Iyer", "Das", "Ghosh"]

regions = np.random.choice(list(region_names.keys()), size=NUM_CUSTOMERS)

# Prepare empty arrays
data_gb = np.zeros(NUM_CUSTOMERS)
minutes = np.zeros(NUM_CUSTOMERS)
sms = np.zeros(NUM_CUSTOMERS)
spend = np.zeros(NUM_CUSTOMERS)

# Vectorized generation for each region group
high_mask = np.isin(regions, ["Delhi", "Mumbai"])
mid_mask = np.isin(regions, ["Bangalore", "Hyderabad", "Chennai"])
low_mask = np.isin(regions, ["Kolkata", "Pune", "Ahmedabad"])

# High spend
data_gb[high_mask] = np.round(np.random.uniform(50, 250, high_mask.sum()), 2)
minutes[high_mask] = np.round(np.random.uniform(1000, 4000, high_mask.sum()), 2)
sms[high_mask] = np.round(np.random.uniform(500, 2000, high_mask.sum()), 2)
spend[high_mask] = np.round(np.random.uniform(799, 1999, high_mask.sum()), 2)

# Mid spend
data_gb[mid_mask] = np.round(np.random.uniform(20, 120, mid_mask.sum()), 2)
minutes[mid_mask] = np.round(np.random.uniform(500, 2500, mid_mask.sum()), 2)
sms[mid_mask] = np.round(np.random.uniform(200, 1200, mid_mask.sum()), 2)
spend[mid_mask] = np.round(np.random.uniform(399, 1299, mid_mask.sum()), 2)

# Low spend
data_gb[low_mask] = np.round(np.random.uniform(1, 60, low_mask.sum()), 2)
minutes[low_mask] = np.round(np.random.uniform(50, 1500, low_mask.sum()), 2)
sms[low_mask] = np.round(np.random.uniform(0, 800, low_mask.sum()), 2)
spend[low_mask] = np.round(np.random.uniform(99, 799, low_mask.sum()), 2)

# Generate names vectorized
names = [
    f"{random.choice(region_names[region])} {random.choice(last_names)}"
    for region in regions
]

# Create DataFrame
df = pd.DataFrame({
    "customer_id": np.arange(1, NUM_CUSTOMERS + 1),
    "name": names,
    "region": regions,
    "avg_monthly_data_gb": data_gb,
    "avg_monthly_minutes": minutes,
    "avg_monthly_sms": sms,
    "avg_monthly_spend": spend
})

# Ensure directory exists
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
df.to_csv(OUTPUT_PATH, index=False)

print(f"Generated {NUM_CUSTOMERS} customers in {OUTPUT_PATH}")
