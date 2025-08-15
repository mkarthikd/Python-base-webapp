# Telecom Customer Insights (Python + Flask)

A sample analytics service for ~50k–100k telecom customers. 
It analyzes usage and recommends the best plan, with a roadmap to plug in ML and LLM later.

## Features
- Synthetic dataset generator (50k–100k records).
- Rule-based plan recommendation API (ready to be upgraded to ML).
- CI: build + test + Snyk code & container scan + push image to Docker Hub.
- CD: deploy to MicroK8s via GitHub Actions.
- Kubernetes manifests (Deployment + Service + Namespace).

## Quick Start (Local)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app/app.py
# http://localhost:5000/health
```

## Generate Data
```bash
python app/data/generate_synthetic.py --rows 100000 --out app/data/customers.csv
```

## Docker
```bash
docker build -t <dockerhub-username>/telecom-customer-insights:latest .
docker run -p 5000:5000 <dockerhub-username>/telecom-customer-insights:latest
```

## Kubernetes (MicroK8s)
```bash
# Ensure your kubeconfig is set and context points to microk8s
kubectl apply -k k8s
# To update image after a new push:
kubectl set image deployment/telecom-api telecom-api=<dockerhub-username>/telecom-customer-insights:<tag>
```

## GitHub Actions — Secrets to Configure
Create these **Repository Secrets**:
- `DOCKERHUB_USERNAME` — your Docker Hub username
- `DOCKERHUB_TOKEN` — a token or password with push permissions
- `SNYK_TOKEN` — from https://app.snyk.io
- `KUBE_CONFIG` — contents of your kubeconfig that can reach your MicroK8s cluster

## Workflows
- **CI (`ci.yml`)**: Runs on push to `main`. Installs deps, tests, Snyk scans, builds and pushes Docker image.
- **CD (`cd.yml`)**: Manual trigger (`workflow_dispatch`) to deploy to MicroK8s using `KUBE_CONFIG` and selected image tag.

## API Endpoints
- `GET /health` — health check
- `GET /customers?limit=100` — sample customers
- `GET /recommend/<customer_id>` — plan recommendation + rationale

## Plan
Basic rule-based plans (to be replaced with ML later):
- **Basic**: light data/voice usage
- **Standard**: moderate usage
- **Premium**: heavy usage

## Roadmap to ML & LLM
- Train a classifier/regressor to predict churn/ARPU/plan fit using `customers.csv`.
- Serve model with FastAPI/Flask; persist artifacts with `joblib`.
- Add an LLM-backed `/advisor` endpoint for plan explanations and upsell scripts.
