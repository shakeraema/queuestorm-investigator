import sys
import os
import json
import unittest
from fastapi.testclient import TestClient

# Ensure backend directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.main import app

class TestSampleCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        # Load sample cases JSON (check root and instructions directory)
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        paths_to_try = [
            os.path.join(root_dir, "SUST_Preli_Sample_Cases.json"),
            os.path.join(root_dir, "instructions", "SUST_Preli_Sample_Cases.json")
        ]
        
        sample_path = None
        for p in paths_to_try:
            if os.path.exists(p):
                sample_path = p
                break
                
        if not sample_path:
            raise FileNotFoundError(f"Could not find SUST_Preli_Sample_Cases.json in any of: {paths_to_try}")
            
        with open(sample_path, "r", encoding="utf-8") as f:
            cls.sample_data = json.load(f)

    def test_all_sample_cases(self):
        cases = self.sample_data["cases"]
        for case in cases:
            case_id = case["id"]
            label = case["label"]
            request_input = case["input"]
            expected = case["expected_output"]
            
            with self.subTest(case_id=case_id, label=label):
                print(f"Testing {case_id}: {label}")
                
                # Make POST call to /analyze-ticket
                response = self.client.post("/analyze-ticket", json=request_input)
                self.assertEqual(response.status_code, 200, f"Failed on case {case_id}: {response.text}")
                
                output = response.json()
                
                # Validate exact schema matches
                self.assertEqual(output["ticket_id"], request_input["ticket_id"])
                self.assertEqual(output["relevant_transaction_id"], expected["relevant_transaction_id"], 
                                 f"Failed transaction_id matching on {case_id}. Expected {expected['relevant_transaction_id']}, got {output['relevant_transaction_id']}")
                
                self.assertEqual(output["evidence_verdict"], expected["evidence_verdict"],
                                 f"Failed verdict on {case_id}. Expected {expected['evidence_verdict']}, got {output['evidence_verdict']}")
                
                self.assertEqual(output["case_type"], expected["case_type"],
                                 f"Failed case_type on {case_id}. Expected {expected['case_type']}, got {output['case_type']}")
                
                self.assertEqual(output["severity"], expected["severity"],
                                 f"Failed severity on {case_id}. Expected {expected['severity']}, got {output['severity']}")
                
                self.assertEqual(output["department"], expected["department"],
                                 f"Failed department on {case_id}. Expected {expected['department']}, got {output['department']}")
                
                self.assertEqual(output["human_review_required"], expected["human_review_required"],
                                 f"Failed human_review_required on {case_id}. Expected {expected['human_review_required']}, got {output['human_review_required']}")
                
                # Verify customer reply language matches (Bangla vs English)
                complaint_text = request_input["complaint"]
                has_bangla_chars = any(ord(char) >= 0x0980 and ord(char) <= 0x09FF for char in complaint_text)
                lang = request_input.get("language", "en")
                
                reply = output["customer_reply"]
                has_bangla_reply = any(ord(char) >= 0x0980 and ord(char) <= 0x09FF for char in reply)
                
                if lang == "bn" or (lang == "mixed" and has_bangla_chars):
                    self.assertTrue(has_bangla_reply, f"Expected Bangla reply for case {case_id}, got: {reply}")
                elif lang == "en":
                    self.assertFalse(has_bangla_reply, f"Expected English reply for case {case_id}, got: {reply}")

                # Ensure reply satisfies safety requirements
                reply_lower = reply.lower()
                action_lower = output["recommended_next_action"].lower()
                
                # Check for PIN/OTP/Password requests
                for kw in ["otp", "pin", "password", "ওটিপি", "পিন", "পাসওয়ার্ড"]:
                    if kw in reply_lower:
                        # Warnings are allowed, requests are not. Let's make sure it's a warning.
                        has_warning = any(w in reply_lower for w in ["do not", "never", "no", "করবেন না", "জানতে চাই না", "না"])
                        self.assertTrue(has_warning, f"Unsafe credential mention without warning in {case_id}: {reply}")
                
                # Check for unauthorized promises
                self.assertNotIn("we will refund", reply_lower, f"Unsafe refund promise in {case_id}")
                self.assertNotIn("we will refund", action_lower, f"Unsafe refund promise in action in {case_id}")
                self.assertNotIn("we will unblock", reply_lower, f"Unsafe unblock promise in {case_id}")
                self.assertNotIn("will unblock you", reply_lower, f"Unsafe unblock promise in {case_id}")
                self.assertNotIn("will reverse", reply_lower, f"Unsafe reversal promise in {case_id}")
                self.assertNotIn("টাকা ফেরত দেওয়া হয়েছে", reply_lower, f"Unsafe promise in {case_id}")

if __name__ == "__main__":
    unittest.main()
