import sys
import os
import unittest
from fastapi.testclient import TestClient

# Ensure backend directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.main import app

class TestApiSkeleton(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_analyze_ticket_skeleton(self):
        payload = {
            "ticket_id": "TKT-TEST-01",
            "complaint": "My transaction failed, please help me."
        }
        response = self.client.post("/analyze-ticket", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["ticket_id"], "TKT-TEST-01")
        self.assertIsNone(data["relevant_transaction_id"])
        self.assertEqual(data["evidence_verdict"], "insufficient_data")
        self.assertEqual(data["case_type"], "other")
        self.assertEqual(data["severity"], "low")
        self.assertEqual(data["department"], "customer_support")
        self.assertFalse(data["human_review_required"])
        self.assertIn("no_transaction_history", data["reason_codes"])

    def test_analyze_ticket_missing_required_fields(self):
        # Missing complaint
        payload = {
            "ticket_id": "TKT-TEST-02"
        }
        response = self.client.post("/analyze-ticket", json=payload)
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)
        self.assertIn("Missing required fields", data["error"])

    def test_analyze_ticket_empty_complaint(self):
        # Empty complaint
        payload = {
            "ticket_id": "TKT-TEST-03",
            "complaint": "   "
        }
        response = self.client.post("/analyze-ticket", json=payload)
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertIn("error", data)
        self.assertIn("cannot be empty", data["error"])

if __name__ == "__main__":
    unittest.main()
