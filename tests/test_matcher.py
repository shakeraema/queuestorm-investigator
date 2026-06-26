import sys
import os
import unittest

# Ensure backend directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.schemas.ticket import TransactionHistoryEntry
from app.services.matcher import TransactionMatcher, extract_amounts, extract_phone_numbers

class TestTransactionMatcher(unittest.TestCase):
    def test_extract_amounts(self):
        self.assertEqual(extract_amounts("I sent 5000 taka to wrong number"), [5000.0])
        self.assertEqual(extract_amounts("আমি ২০০০ টাকা ক্যাশ ইন করেছি"), [2000.0])
        self.assertEqual(extract_amounts("I paid 500 to a merchant"), [500.0])
        # 11-digit phone number starting with 01 should be ignored as amount
        self.assertEqual(extract_amounts("I sent 5000 BDT to 01712345678"), [5000.0])

    def test_extract_phones(self):
        self.assertEqual(extract_phone_numbers("My brother number is 01712345678"), ["01712345678"])
        self.assertEqual(extract_phone_numbers("Please send to +8801812345678"), ["01812345678"])

    def test_sample_01_wrong_transfer_consistent(self):
        complaint = "I sent 5000 taka to a wrong number around 2pm today. The number was supposed to be 01712345678 but I think I typed it wrong. The person isn't responding to my call. Please help me get my money back."
        history = [
            TransactionHistoryEntry(
                transaction_id="TXN-9101",
                timestamp="2026-04-14T14:08:22Z",
                type="transfer",
                amount=5000,
                counterparty="+8801719876543",
                status="completed"
            ),
            TransactionHistoryEntry(
                transaction_id="TXN-9087",
                timestamp="2026-04-13T18:12:00Z",
                type="cash_in",
                amount=10000,
                counterparty="AGENT-512",
                status="completed"
            )
        ]
        tx, verdict, reasons = TransactionMatcher.match_transaction(complaint, history)
        self.assertIsNotNone(tx)
        self.assertEqual(tx.transaction_id, "TXN-9101")
        self.assertEqual(verdict, "consistent")

    def test_sample_02_wrong_transfer_inconsistent(self):
        complaint = "I sent 2000 to the wrong person by mistake. Please reverse it."
        history = [
            TransactionHistoryEntry(
                transaction_id="TXN-9202",
                timestamp="2026-04-14T11:30:00Z",
                type="transfer",
                amount=2000,
                counterparty="+8801812345678",
                status="completed"
            ),
            TransactionHistoryEntry(
                transaction_id="TXN-9180",
                timestamp="2026-04-10T09:15:00Z",
                type="transfer",
                amount=2500,
                counterparty="+8801812345678",
                status="completed"
            ),
            TransactionHistoryEntry(
                transaction_id="TXN-9145",
                timestamp="2026-04-05T17:45:00Z",
                type="transfer",
                amount=1500,
                counterparty="+8801812345678",
                status="completed"
            )
        ]
        tx, verdict, reasons = TransactionMatcher.match_transaction(complaint, history)
        self.assertIsNotNone(tx)
        self.assertEqual(tx.transaction_id, "TXN-9202")
        self.assertEqual(verdict, "inconsistent")

    def test_sample_03_failed_payment_deducted(self):
        complaint = "I tried to pay 1200 taka for my mobile recharge but the app showed failed. But my balance was deducted! Please refund my money."
        history = [
            TransactionHistoryEntry(
                transaction_id="TXN-9301",
                timestamp="2026-04-14T16:00:00Z",
                type="payment",
                amount=1200,
                counterparty="MERCHANT-MOBILE-OP",
                status="failed"
            )
        ]
        tx, verdict, reasons = TransactionMatcher.match_transaction(complaint, history)
        self.assertIsNotNone(tx)
        self.assertEqual(tx.transaction_id, "TXN-9301")
        self.assertEqual(verdict, "consistent")

    def test_sample_05_phishing_insufficient_data(self):
        complaint = "Someone called me saying they are from bKash and asked for my OTP. They said my account will be blocked if I don't share it. Is this real? I haven't shared anything yet."
        history = []
        tx, verdict, reasons = TransactionMatcher.match_transaction(complaint, history)
        self.assertIsNone(tx)
        self.assertEqual(verdict, "insufficient_data")

    def test_sample_08_ambiguous_transactions(self):
        complaint = "I sent 1000 to my brother yesterday but he says he didn't get it. Please check."
        history = [
            TransactionHistoryEntry(
                transaction_id="TXN-9801",
                timestamp="2026-04-13T11:20:00Z",
                type="transfer",
                amount=1000,
                counterparty="+8801712001122",
                status="completed"
            ),
            TransactionHistoryEntry(
                transaction_id="TXN-9802",
                timestamp="2026-04-13T19:45:00Z",
                type="transfer",
                amount=1000,
                counterparty="+8801812334455",
                status="completed"
            ),
            TransactionHistoryEntry(
                transaction_id="TXN-9803",
                timestamp="2026-04-13T20:10:00Z",
                type="transfer",
                amount=1000,
                counterparty="+8801712001122",
                status="failed"
            )
        ]
        tx, verdict, reasons = TransactionMatcher.match_transaction(complaint, history)
        self.assertIsNone(tx)
        self.assertEqual(verdict, "insufficient_data")
        self.assertIn("ambiguous_match", reasons)

    def test_sample_10_duplicate_payment(self):
        complaint = "I paid my electricity bill 850 taka but it deducted twice from my account. Please check, I only paid once."
        history = [
            TransactionHistoryEntry(
                transaction_id="TXN-10001",
                timestamp="2026-04-14T08:15:30Z",
                type="payment",
                amount=850,
                counterparty="BILLER-DESCO",
                status="completed"
            ),
            TransactionHistoryEntry(
                transaction_id="TXN-10002",
                timestamp="2026-04-14T08:15:42Z",
                type="payment",
                amount=850,
                counterparty="BILLER-DESCO",
                status="completed"
            )
        ]
        tx, verdict, reasons = TransactionMatcher.match_transaction(complaint, history)
        self.assertIsNotNone(tx)
        # It should match the second transaction since it represents the duplicate
        self.assertEqual(tx.transaction_id, "TXN-10002")
        self.assertEqual(verdict, "consistent")

if __name__ == "__main__":
    unittest.main()
