import re
import logging
from typing import Optional, Dict, Any, Tuple
from app.schemas.ticket import (
    TransactionHistoryEntry,
    CaseType,
    SeverityType,
    DepartmentType,
    EvidenceVerdictType
)
from app.services.matcher import normalize_text

logger = logging.getLogger("queuestorm.classifier")

class CaseClassifier:
    @staticmethod
    def classify(
        complaint: str,
        user_type: Optional[str],
        matched_tx: Optional[TransactionHistoryEntry],
        verdict: EvidenceVerdictType
    ) -> Tuple[CaseType, SeverityType, DepartmentType, bool]:
        """
        Classifies the ticket based on complaint text and matching results.
        Returns:
            Tuple[case_type, severity, department, human_review_required]
        """
        norm_complaint = normalize_text(complaint)
        user_type_lower = user_type.lower() if user_type else "unknown"

        # 1. PHISHING / SOCIAL ENGINEERING DETECTION (Highest Priority)
        # Matches someone asking for sensitive details, claiming to be bKash, blocking account
        phishing_kws = [
            "otp", "pin", "password", "credential", "verification code", "card number",
            "ওটিপি", "পিন", "পাসওয়ার্ড", "কার্ড নাম্বার", "ভেরিফিকেশন",
            "blocked", "block", "সাসপেন্ড", "ব্লক", "অ্যাকাউন্ট বন্ধ"
        ]
        is_phishing = any(kw in norm_complaint for kw in phishing_kws) and any(
            x in norm_complaint for x in ["ask", "call", "send", "share", "চাই", "চেয়েছে", "বলছে", "বলল", "দিতে"]
        )
        
        # Also direct phishing reports
        if is_phishing or any(kw in norm_complaint for kw in ["phishing", "scam", "fraud", "প্রতারণা", "ফিশিং", "ভুয়া"]):
            logger.info("Classified as phishing_or_social_engineering")
            return "phishing_or_social_engineering", "critical", "fraud_risk", True

        # 2. MATCHED TRANSACTION INDICATIONS
        tx_type = matched_tx.type.lower() if matched_tx else None
        tx_status = matched_tx.status.lower() if matched_tx else None

        # 3. DETECT CASE TYPE
        case_type: CaseType = "other"
        
        # Check specific text conditions first to be robust against missing transactions (insufficient data)
        is_wrong_transfer_text = (
            any(kw in norm_complaint for kw in ["wrong number", "wrong recipient", "wrong person", "wrong transfer", "wrongly sent", "sent to wrong", "wrong account"]) or
            (any(kw in norm_complaint for kw in ["sent", "send", "transfer"]) and "wrong" in norm_complaint) or
            any(kw in norm_complaint for kw in ["ভুল নাম্বারে", "ভুল নম্বরে", "ভুল একাউন্টে", "ভুল করে"])
        )
        is_transfer_not_received = (
            any(kw in norm_complaint for kw in ["sent", "send", "transfer", "পাঠা"]) and
            any(kw in norm_complaint for kw in ["didn't get", "did not get", "not receive", "says he didn't", "পায়নি", "পায় নাই", "আসেনি"])
        )

        # Wrong Transfer
        if is_wrong_transfer_text or is_transfer_not_received or tx_type == "transfer":
            case_type = "wrong_transfer"
        # Duplicate Payment
        elif any(kw in norm_complaint for kw in ["twice", "double", "২ বার", "দুইবার", "ডাবল", "duplicate", "ডুপ্লিকেট"]):
            case_type = "duplicate_payment"
        # Failed Payment (checked before refund_request to handle refund mentions on failed recharges)
        elif (tx_status == "failed" or 
              ((tx_type == "payment" or any(kw in norm_complaint for kw in ["payment", "pay", "recharge", "bill", "পেমেন্ট", "রিচার্জ", "বিল"])) and
               any(kw in norm_complaint for kw in ["failed", "fail", "ব্যর্থ", "কেটেছে", "ডিকাডক্ট", "deduct", "হয়নি"]))):
            case_type = "payment_failed"
        # Refund Request
        elif any(kw in norm_complaint for kw in ["refund", "return", "রিফান্ড", "ফেরত", "changed my mind", "change my mind", "changed mind", "don't want", "don't need", "মন পরিবর্তন", "চাই না", "লাগবে না"]):
            case_type = "refund_request"
        # Agent Cash In
        elif tx_type == "cash_in" or any(kw in norm_complaint for kw in ["cash-in", "cash in", "এজেন্ট", "ক্যাশ ইন", "ক্যাশইন"]):
            case_type = "agent_cash_in_issue"
        # Merchant Settlement
        elif user_type_lower == "merchant" or tx_type == "settlement" or any(kw in norm_complaint for kw in ["settle", "settlement", "সেটেলমেন্ট", "মার্চেন্ট"]):
            case_type = "merchant_settlement_delay"
        # Defaults based on matched tx type
        elif tx_type == "payment":
            case_type = "payment_failed" if tx_status == "failed" else "refund_request"
        elif tx_type == "cash_in":
            case_type = "agent_cash_in_issue"
        elif tx_type == "settlement":
            case_type = "merchant_settlement_delay"

        # 4. ROUTING DEPARTMENT (Section 7.2)
        department: DepartmentType = "customer_support"
        if case_type == "phishing_or_social_engineering":
            department = "fraud_risk"
        elif case_type == "agent_cash_in_issue":
            department = "agent_operations"
        elif case_type == "merchant_settlement_delay":
            department = "merchant_operations"
        elif case_type in ["payment_failed", "duplicate_payment"]:
            department = "payments_ops"
        elif case_type == "wrong_transfer":
            department = "dispute_resolution"
        elif case_type == "refund_request":
            # Direct refunds are dispute_resolution, low-severity change of mind are customer_support
            if any(kw in norm_complaint for kw in ["changed my mind", "change my mind", "changed mind", "don't want", "don't need", "মন পরিবর্তন", "চাই না", "লাগবে না"]):
                department = "customer_support"
            else:
                department = "dispute_resolution"

        # Override for vague/insufficient_data cases: always route to customer_support
        if verdict == "insufficient_data" and case_type == "other":
            department = "customer_support"

        # 5. SEVERITY ASSIGNMENT
        severity: SeverityType = "low"
        if case_type == "phishing_or_social_engineering":
            severity = "critical"
        elif case_type == "wrong_transfer":
            if verdict == "consistent":
                severity = "high"
            else:
                severity = "medium"
        elif case_type == "payment_failed":
            severity = "high"
        elif case_type == "duplicate_payment":
            severity = "high"
        elif case_type == "agent_cash_in_issue":
            severity = "high"
        elif case_type == "merchant_settlement_delay":
            severity = "medium"
        elif case_type == "refund_request":
            severity = "low"
        
        # 6. HUMAN REVIEW ESCALATION
        # Rule: True for disputes (wrong transfer, duplicate payment, agent cash-in), suspicious cases (phishing),
        # high value cases, or inconsistent evidence.
        # False for: simple payment failures, low-severity refund change of mind, vague/insufficient data cases
        human_review_required = False
        if case_type == "phishing_or_social_engineering":
            human_review_required = True
        elif case_type == "wrong_transfer":
            # If verdict is insufficient_data due to ambiguous matching, we ask customer first (no human review yet, false).
            # If verdict is consistent or inconsistent, it is initiated/flagged -> human review true.
            if verdict in ["consistent", "inconsistent"]:
                human_review_required = True
        elif case_type == "duplicate_payment" and verdict == "consistent":
            human_review_required = True
        elif case_type == "agent_cash_in_issue" and verdict == "consistent":
            human_review_required = True
        elif verdict == "inconsistent":
            human_review_required = True

        logger.info(f"Classified: case_type={case_type}, severity={severity}, dept={department}, human_review={human_review_required}")
        return case_type, severity, department, human_review_required
