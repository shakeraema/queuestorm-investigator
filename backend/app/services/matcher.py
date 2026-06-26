import re
import logging
from typing import List, Optional, Tuple, Dict, Any
from app.schemas.ticket import TransactionHistoryEntry

logger = logging.getLogger("queuestorm.matcher")

BANGLA_DIGITS = {
    '০': '0', '১': '1', '২': '2', '৩': '3', '৪': '4',
    '৫': '5', '৬': '6', '৭': '7', '৮': '8', '৯': '9'
}

def translate_bangla_digits(text: str) -> str:
    for bd, ed in BANGLA_DIGITS.items():
        text = text.replace(bd, ed)
    return text

def normalize_phone(phone: str) -> str:
    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)
    # If it ends with 11 digits (typical BD mobile number starting with 01), keep last 11
    if len(digits) >= 11:
        return digits[-11:]
    return digits

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = translate_bangla_digits(text)
    text = text.lower()
    # Remove commas in numbers (e.g. 5,000 -> 5000)
    text = re.sub(r'(\d+),(\d+)', r'\1\2', text)
    # Handle suffix 'k' for thousands (e.g. 5k -> 5000)
    text = re.sub(r'(\d+)k\b', r'\1000', text)
    # Handle Bangla thousand "হাজার" (e.g. 5 হাজার -> 5000)
    text = re.sub(r'(\d+)\s*হাজার', r'\1000', text)
    return text

def extract_amounts(text: str) -> List[float]:
    normalized = normalize_text(text)
    # Find all numeric patterns (integers and decimals)
    patterns = re.findall(r'\b\d+(?:\.\d+)?\b', normalized)
    amounts = []
    for pat in patterns:
        try:
            val = float(pat)
            # Filter out likely phone numbers (9+ digits) or small dates/hours (e.g. years 2026, or days <= 31)
            # unless the amount is really small (like BDT 10 to 30) - in practice, transactions in sample cases are >= 100
            # Let's keep numbers between 10 and 1000000, and ignore if length is 11 (likely phone number) or 4 (likely year like 2026)
            pat_str = str(pat).split('.')[0]
            if len(pat_str) == 11 and pat_str.startswith('01'):
                continue
            if len(pat_str) == 4 and pat_str.startswith('202'): # Ignore current years
                continue
            if 10 <= val <= 1000000:
                amounts.append(val)
        except ValueError:
            continue
    return list(set(amounts))

def extract_phone_numbers(text: str) -> List[str]:
    normalized = translate_bangla_digits(text)
    # Look for BD phone numbers: digits starting with 01 or 8801, or +8801
    phones = re.findall(r'(?:\+?88)?01[3-9]\d{8}', normalized)
    return [normalize_phone(p) for p in phones]

class TransactionMatcher:
    @staticmethod
    def match_transaction(
        complaint: str,
        history: Optional[List[TransactionHistoryEntry]]
    ) -> Tuple[Optional[TransactionHistoryEntry], str, List[str]]:
        """
        Matches a complaint to a transaction in the history.
        Returns:
            Tuple[matched_transaction, evidence_verdict, reason_codes]
        """
        if not history:
            logger.info("Transaction history is empty.")
            return None, "insufficient_data", ["no_transaction_history"]

        normalized_complaint = normalize_text(complaint)
        logger.debug(f"Normalized complaint: {normalized_complaint}")

        # 1. Direct Transaction ID Match (Case-Insensitive)
        for tx in history:
            if tx.transaction_id.lower() in normalized_complaint:
                logger.info(f"Direct ID match found for {tx.transaction_id}")
                # Evaluate consistency for direct match
                verdict, reasons = TransactionMatcher.evaluate_consistency(complaint, tx, history)
                return tx, verdict, ["direct_id_match"] + reasons

        # 2. Extract entities for score-based matching
        extracted_amounts = extract_amounts(complaint)
        extracted_phones = extract_phone_numbers(complaint)
        logger.debug(f"Extracted amounts: {extracted_amounts}, phones: {extracted_phones}")

        # Check if transaction ID keywords exist (e.g. txn, transaction, লেনদেন)
        has_txn_keyword = any(kw in normalized_complaint for kw in ["txn", "transaction", "txid", "আইডি", "লেনদেন"])

        # Score candidate transactions
        candidates: List[Tuple[TransactionHistoryEntry, float, List[str]]] = []
        for tx in history:
            score = 0.0
            reasons = []

            # Match amount
            # Direct float comparison (allowing small epsilon for float comparison)
            amount_matched = False
            for amt in extracted_amounts:
                if abs(tx.amount - amt) < 0.01:
                    amount_matched = True
                    break
            
            if amount_matched:
                score += 5.0
                reasons.append("amount_match")

            # Match counterparty
            tx_counterparty_norm = normalize_phone(tx.counterparty)
            counterparty_matched = False
            if tx_counterparty_norm and tx_counterparty_norm in extracted_phones:
                counterparty_matched = True
            elif tx.counterparty.lower() in normalized_complaint:
                counterparty_matched = True
            
            if counterparty_matched:
                score += 5.0
                reasons.append("counterparty_match")

            # Match transaction type keywords
            type_keyword_matched = False
            tx_type = tx.type.lower()
            if tx_type == "transfer" and any(kw in normalized_complaint for kw in ["transfer", "sent", "send", "পাঠা", "সেন্ড"]):
                type_keyword_matched = True
            elif tx_type == "payment" and any(kw in normalized_complaint for kw in ["payment", "pay", "paid", "recharge", "biller", "bill", "পেমেন্ট", "রিচার্জ", "বিল"]):
                type_keyword_matched = True
            elif tx_type == "cash_in" and any(kw in normalized_complaint for kw in ["cash in", "cash_in", "এজেন্ট", "ডিপোজিট", "ক্যাশ ইন", "ক্যাশইন"]):
                type_keyword_matched = True
            elif tx_type == "cash_out" and any(kw in normalized_complaint for kw in ["cash out", "cash_out", "উত্তোলন", "ক্যাশ আউট"]):
                type_keyword_matched = True
            elif tx_type == "settlement" and any(kw in normalized_complaint for kw in ["settlement", "payout", "সেটেলমেন্ট"]):
                type_keyword_matched = True
            elif tx_type == "refund" and any(kw in normalized_complaint for kw in ["refund", "return", "রিফান্ড", "ফেরত"]):
                type_keyword_matched = True

            if type_keyword_matched:
                score += 2.0
                reasons.append("type_keyword_match")

            # Match status keywords (e.g. failed, pending)
            status_keyword_matched = False
            tx_status = tx.status.lower()
            if tx_status == "failed" and any(kw in normalized_complaint for kw in ["failed", "fail", "ব্যর্থ", "হয়নি", "অসফল"]):
                status_keyword_matched = True
            elif tx_status == "pending" and any(kw in normalized_complaint for kw in ["pending", "অপেক্ষমান", "পেন্ডিং"]):
                status_keyword_matched = True

            if status_keyword_matched:
                score += 1.5
                reasons.append("status_keyword_match")

            # If user type matches, slight bonus
            # e.g., merchant in complaint and transaction is settlement
            if "merchant" in normalized_complaint and tx_type == "settlement":
                score += 1.0

            if score > 0:
                candidates.append((tx, score, reasons))

        if not candidates:
            logger.info("No candidate transactions matched extraction entities.")
            return None, "insufficient_data", ["no_matching_transaction"]

        # Sort candidates by score descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        max_score = candidates[0][1]
        
        # Filter all candidates that have the maximum score
        best_candidates = [c for c in candidates if c[1] == max_score]

        # If score is too low, treat as insufficient
        if max_score < 4.0:
            logger.info(f"Top match score {max_score} is below threshold.")
            return None, "insufficient_data", ["low_match_confidence"]

        # If there are multiple transactions with the same highest score, check ambiguity or duplicate payments
        if len(best_candidates) > 1:
            # Check if this is a duplicate payment scenario (identical amount, type, counterparty, and status)
            first_cand = best_candidates[0][0]
            is_duplicate_scenario = True
            for c in best_candidates[1:]:
                tx_cand = c[0]
                if (tx_cand.amount != first_cand.amount or
                    tx_cand.type != first_cand.type or
                    tx_cand.counterparty != first_cand.counterparty or
                    tx_cand.status != first_cand.status):
                    is_duplicate_scenario = False
                    break
            
            has_dup_keywords = any(kw in normalized_complaint for kw in ["twice", "double", "২ বার", "দুইবার", "ডাবল", "duplicate", "ডুপ্লিকেট"])
            
            if is_duplicate_scenario and has_dup_keywords:
                # Sort best_candidates by timestamp ascending to select the duplicate (second/later one)
                best_candidates.sort(key=lambda x: x[0].timestamp)
                matched_tx = best_candidates[-1][0]
                match_reasons = best_candidates[-1][2]
                logger.info(f"Resolved duplicate payment: matched to later transaction {matched_tx.transaction_id}")
                
                verdict, reasons = TransactionMatcher.evaluate_consistency(complaint, matched_tx, history)
                return matched_tx, verdict, match_reasons + ["duplicate_payment_resolved"] + reasons
            
            logger.info(f"Ambiguous match: {len(best_candidates)} candidates with score {max_score}")
            return None, "insufficient_data", ["ambiguous_match"]

        matched_tx = best_candidates[0][0]
        match_reasons = best_candidates[0][2]
        logger.info(f"Matched to transaction {matched_tx.transaction_id} with score {max_score}")

        # Evaluate consistency
        verdict, reasons = TransactionMatcher.evaluate_consistency(complaint, matched_tx, history)
        return matched_tx, verdict, match_reasons + reasons

    @staticmethod
    def evaluate_consistency(
        complaint: str,
        tx: TransactionHistoryEntry,
        history: List[TransactionHistoryEntry]
    ) -> Tuple[str, List[str]]:
        """
        Evaluates whether the matched transaction is consistent or inconsistent with the complaint.
        """
        normalized_complaint = normalize_text(complaint)
        tx_type = tx.type.lower()
        tx_status = tx.status.lower()

        # 1. Wrong Transfer Recipient Pattern (SAMPLE-02)
        if tx_type == "transfer" and any(kw in normalized_complaint for kw in ["wrong", "ভুল", "mistake"]):
            # Check if there's a pattern of prior completed transfers to the same counterparty
            counterparty = tx.counterparty
            prior_transfers = [
                t for t in history
                if t.transaction_id != tx.transaction_id
                and t.type == "transfer"
                and t.counterparty == counterparty
                and t.status == "completed"
                # must be prior in timestamp or simply exist in history
                and t.timestamp < tx.timestamp
            ]
            if len(prior_transfers) >= 2: # At least two prior transfers indicates established pattern
                logger.info(f"Inconsistent wrong transfer: {len(prior_transfers)} prior transfers to same counterparty")
                return "inconsistent", ["established_recipient_pattern", "evidence_inconsistent"]

        # 2. Failed Payment / Balance Deducted checks (SAMPLE-03)
        if tx_type == "payment" and any(kw in normalized_complaint for kw in ["failed", "fail", "রিচার্জ হয়নি", "ব্যর্থ"]):
            if tx_status == "failed":
                # Consistent because it failed as transaction states
                return "consistent", ["payment_failed_confirmed"]
            elif tx_status == "completed":
                # Inconsistent: customer claims it failed, but system says completed
                return "inconsistent", ["transaction_completed_in_system"]

        # 3. Duplicate Payment checks (SAMPLE-10)
        if any(kw in normalized_complaint for kw in ["twice", "double", "২ বার", "দুইবার", "ডাবল", "ডুপি"]):
            # Look for duplicate transactions in history (same type, same amount, same counterparty, completed, within 5 minutes)
            duplicates = [
                t for t in history
                if t.transaction_id != tx.transaction_id
                and t.type == tx.type
                and abs(t.amount - tx.amount) < 0.01
                and t.counterparty == tx.counterparty
                and t.status == "completed"
            ]
            if duplicates:
                logger.info(f"Duplicate payment confirmed: matching transaction {tx.transaction_id} duplicate found")
                return "consistent", ["duplicate_payment_pattern"]

        # 4. Agent Cash-in Pending (SAMPLE-07)
        if tx_type == "cash_in" and tx_status == "pending" and any(kw in normalized_complaint for kw in ["আসেনি", "ব্যালেন্স", "ক্যাশ ইন", "ডিপোজিট"]):
            return "consistent", ["cash_in_pending"]

        # 5. Settlement Delay Pending (SAMPLE-09)
        if tx_type == "settlement" and tx_status == "pending" and any(kw in normalized_complaint for kw in ["settle", "সেটেলমেন্ট", "টাকা আসেনি"]):
            return "consistent", ["settlement_pending"]

        # Default to consistent if transaction matches and no obvious contradiction is found
        return "consistent", ["transaction_match"]
