import unittest
from app.model.recommender import recommend_plan

class TestRecommender(unittest.TestCase):
    def test_basic(self):
        customer = {'customer_id': 1, 'avg_monthly_data_gb': 5, 'avg_monthly_minutes': 100, 'avg_monthly_sms': 50, 'avg_monthly_spend': 399}
        rec = recommend_plan(customer)
        assert rec['recommended_plan'] == 'Basic'

    def test_standard(self):
        customer = {'customer_id': 2, 'avg_monthly_data_gb': 40, 'avg_monthly_minutes': 800, 'avg_monthly_sms': 300, 'avg_monthly_spend': 699}
        rec = recommend_plan(customer)
        assert rec['recommended_plan'] == 'Standard'

    def test_premium(self):
        customer = {'customer_id': 3, 'avg_monthly_data_gb': 120, 'avg_monthly_minutes': 2500, 'avg_monthly_sms': 1200, 'avg_monthly_spend': 1299}
        rec = recommend_plan(customer)
        assert rec['recommended_plan'] == 'Premium'
