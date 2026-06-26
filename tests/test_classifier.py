import sys
import os
import unittest

# Ensure backend directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.schemas.ticket import TransactionHistoryEntry
from app.services.classifier import CaseClassifier

class TestCaseClassifier(unittest.TestCase):
    def test_sample_01_wrong_transfer(self):
        complaint = "I sent 5000 taka to a wrong number around 2pm today..."
        tx = TransactionHistoryEntry(
            transaction_id="TXN-9101",
            timestamp="2026-04-14T14:08:22Z",
            type="transfer",
            amount=5000,
            counterparty="+8801719876543",
            status="completed"
        )
        case_type, severity, department, human_review = CaseClassifier.classify(
            complaint, "customer", tx, "consistent"
        )
        self.assertEqual(case_type, "wrong_transfer")
        self.assertEqual(severity, "high")
        self.assertEqual(department, "dispute_resolution")
        self.assertTrue(human_review)

    def test_sample_02_wrong_transfer_inconsistent(self):
        complaint = "I sent 2000 to the wrong person by mistake. Please reverse it."
        tx = TransactionHistoryEntry(
            transaction_id="TXN-9202",
            timestamp="2026-04-14T11:30:00Z",
            type="transfer",
            amount=2000,
            counterparty="+8801812345678",
            status="completed"
        )
        case_type, severity, department, human_review = CaseClassifier.classify(
            complaint, "customer", tx, "inconsistent"
        )
        self.assertEqual(case_type, "wrong_transfer")
        self.assertEqual(severity, "medium")
        self.assertEqual(department, "dispute_resolution")
        self.assertTrue(human_review)

    def test_sample_03_payment_failed(self):
        complaint = "I tried to pay 1200 taka for my mobile recharge but the app showed failed. But my balance was deducted!"
        tx = TransactionHistoryEntry(
            transaction_id="TXN-9301",
            timestamp="2026-04-14T16:00:00Z",
            type="payment",
            amount=1200,
            counterparty="MERCHANT-MOBILE-OP",
            status="failed"
        )
        case_type, severity, department, human_review = CaseClassifier.classify(
            complaint, "customer", tx, "consistent"
        )
        self.assertEqual(case_type, "payment_failed")
        self.assertEqual(severity, "high")
        self.assertEqual(department, "payments_ops")
        self.assertFalse(human_review)

    def test_sample_04_refund_request(self):
        complaint = "I paid 500 to a merchant for a product but I changed my mind..."
        tx = TransactionHistoryEntry(
            transaction_id="TXN-9401",
            timestamp="2026-04-14T13:00:00Z",
            type="payment",
            amount=500,
            counterparty="MERCHANT-7821",
            status="completed"
        )
        case_type, severity, department, human_review = CaseClassifier.classify(
            complaint, "customer", tx, "consistent"
        )
        self.assertEqual(case_type, "refund_request")
        self.assertEqual(severity, "low")
        self.assertEqual(department, "customer_support")
        self.assertFalse(human_review)

    def test_sample_05_phishing(self):
        complaint = "Someone called me saying they are from bKash and asked for my OTP. They said my account will be blocked..."
        case_type, severity, department, human_review = CaseClassifier.classify(
            complaint, "customer", None, "insufficient_data"
        )
        self.assertEqual(case_type, "phishing_or_social_engineering")
        self.assertEqual(severity, "critical")
        self.assertEqual(department, "fraud_risk")
        self.assertTrue(human_review)

    def test_sample_06_vague_other(self):
        complaint = "Something is wrong with my money. Please check."
        case_type, severity, department, human_review = CaseClassifier.classify(
            complaint, "customer", None, "insufficient_data"
        )
        self.assertEqual(case_type, "other")
        self.assertEqual(severity, "low")
        self.assertEqual(department, "customer_support")
        self.assertFalse(human_review)

    def test_sample_07_agent_cash_in(self):
        complaint = "আমি আজ সকালে এজেন্টের কাছে ২০০০ টাকা ক্যাশ ইন করেছি কিন্তু আমার ব্যালেন্সে টাকা আসেনি।"
        tx = TransactionHistoryEntry(
            transaction_id="TXN-9701",
            timestamp="2026-04-14T09:30:00Z",
            type="cash_in",
            amount=2000,
            counterparty="AGENT-318",
            status="pending"
        )
        case_type, severity, department, human_review = CaseClassifier.classify(
            complaint, "customer", tx, "consistent"
        )
        self.assertEqual(case_type, "agent_cash_in_issue")
        self.assertEqual(severity, "high")
        self.assertEqual(department, "agent_operations")
        self.assertTrue(human_review)

    def test_sample_08_ambiguous_wrong_transfer(self):
        complaint = "I sent 1000 to my brother yesterday but he says he didn't get it."
        case_type, severity, department, human_review = CaseClassifier.classify(
            complaint, "customer", None, "insufficient_data"
        )
        self.assertEqual(case_type, "wrong_transfer")
        self.assertEqual(severity, "medium")
        self.assertEqual(department, "dispute_resolution")
        self.assertFalse(human_review)

    def test_sample_09_merchant_settlement(self):
        complaint = "I am a merchant. My yesterday's sales of 15000 taka have not been settled to my account."
        tx = TransactionHistoryEntry(
            transaction_id="TXN-9901",
            timestamp="2026-04-13T18:00:00Z",
            type="settlement",
            amount=15000,
            counterparty="MERCHANT-SELF",
            status="pending"
        )
        case_type, severity, department, human_review = CaseClassifier.classify(
            complaint, "merchant", tx, "consistent"
        )
        self.assertEqual(case_type, "merchant_settlement_delay")
        self.assertEqual(severity, "medium")
        self.assertEqual(department, "merchant_operations")
        self.assertFalse(human_review)

    def test_sample_10_duplicate_payment(self):
        complaint = "I paid my electricity bill 850 taka but it deducted twice from my account."
        tx = TransactionHistoryEntry(
            transaction_id="TXN-10002",
            timestamp="2026-04-14T08:15:42Z",
            type="payment",
            amount=850,
            counterparty="BILLER-DESCO",
            status="completed"
        )
        case_type, severity, department, human_review = CaseClassifier.classify(
            complaint, "customer", tx, "consistent"
        )
        self.assertEqual(case_type, "duplicate_payment")
        self.assertEqual(severity, "high")
        self.assertEqual(department, "payments_ops")
        self.assertTrue(human_review)

if __name__ == "__main__":
    unittest.main()
