import re
import logging
from typing import Dict, Any, List

logger = logging.getLogger("queuestorm.safety")

# Direct prompt injection words
INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+)?previous\s+instructions",
    r"override\s+(?:all\s+)?rules",
    r"system\s+(?:rules|prompt|instruction)",
    r"you\s+must\s+classify\s+this\s+as",
    r"instead\s+say",
    r"new\s+instruction",
    r"do\s+not\s+classify",
    r"say\s+hello\s+to",
    r"নতুন\s+নির্দেশনা",
    r"পূর্বের\s+নির্দেশনা",
    r"ভুলে\s+যাও"
]

CREDENTIAL_WORDS = [
    "otp", "pin", "password", "passcode", "card number", "cardno", "cvv",
    "ওটিপি", "পিন", "পাসওয়ার্ড", "পাসকোড", "কার্ড নম্বর", "কার্ড নাম্বার"
]

NEGATION_KEYWORDS = [
    "do not", "don't", "dont", "never", "no", "not share", "do not share",
    "never share", "never ask", "করবেন না", "শেয়ার করবেন না", "জানতে চাই না",
    "জানাতে চাই না", "চাই না", "কখনো নয়", "কখনো না", "কখনোই না", "সংরক্ষণ করবেন না"
]

UNSAFE_PROMISE_KEYWORDS = [
    "we will refund", "refunded your", "we have refunded", "money has been reversed",
    "will reverse", "we will unblock", "account has been unblocked", "we recovered",
    "will recover", "will unblock you", "we will refund you", "টাকা ফেরত দেওয়া হয়েছে",
    "রিফান্ড করা হয়েছে", "আমরা রিফান্ড করেছি", "আনব্লক করে দিয়েছি"
]

UNOFFICIAL_CHANNELS = [
    "whatsapp", "telegram", "viber", "imo", "হোয়াটসঅ্যাপ", "টেলিগ্রাম", "ইমো", "ভাইবার"
]

class SafetyEngine:
    @staticmethod
    def detect_prompt_injection(complaint: str) -> bool:
        """
        Scans complaint text for prompt injection signs.
        """
        if not complaint:
            return False
        
        complaint_lower = complaint.lower()
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, complaint_lower):
                logger.warning(f"Prompt injection pattern detected: '{pattern}'")
                return True
        return False

    @staticmethod
    def audit_response(
        customer_reply: str,
        recommended_next_action: str
    ) -> bool:
        """
        Verifies whether response texts satisfy all FinTech safety rules.
        Returns:
            True if response is safe, False if unsafe.
        """
        reply_lower = customer_reply.lower()
        action_lower = recommended_next_action.lower()

        # 1. Unofficial Channels Check (whatsapp, telegram, etc.)
        for channel in UNOFFICIAL_CHANNELS:
            if channel in reply_lower:
                logger.error(f"Safety violation: Unofficial channel '{channel}' mentioned in reply.")
                return False

        # 2. Check phone number patterns that are not official shortcode or official number
        # Block arbitrary 11 digit numbers in customer reply
        phones = re.findall(r'\b\d{7,15}\b', reply_lower)
        for phone in phones:
            if phone not in ["16247", "09638116247"]:
                logger.error(f"Safety violation: Unofficial phone number '{phone}' in customer reply.")
                return False

        # 3. Check unauthorized promises in customer_reply & recommended_next_action
        for promise in UNSAFE_PROMISE_KEYWORDS:
            if promise in reply_lower or promise in action_lower:
                logger.error(f"Safety violation: Unauthorized promise '{promise}' detected.")
                return False

        # Direct absolute blocks
        if "will refund" in reply_lower or "will unblock" in reply_lower or "will reverse" in reply_lower:
            logger.error("Safety violation: Absolute check fail.")
            return False

        # 4. Sentence-by-sentence credential validation
        # Split customer reply into sentences using common punctuation
        sentences = re.split(r'[.!।?]\s*', customer_reply)
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if not sentence_lower.strip():
                continue

            # Check if this sentence contains any credential keyword
            has_credential = any(word in sentence_lower for word in CREDENTIAL_WORDS)
            
            if has_credential:
                # Must contain warning/negation keywords to be permitted
                has_negation = any(neg in sentence_lower for neg in NEGATION_KEYWORDS)
                if not has_negation:
                    logger.error(f"Safety violation: Sentence '{sentence.strip()}' contains credential words but has no negation warnings.")
                    return False

        return True

    @staticmethod
    def sanitize(
        response_data: Dict[str, Any],
        fallback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Audits output fields and automatically applies safe fallbacks if violations are found.
        """
        is_safe = SafetyEngine.audit_response(
            customer_reply=response_data.get("customer_reply", ""),
            recommended_next_action=response_data.get("recommended_next_action", "")
        )

        if not is_safe:
            logger.warning("Unsafe content detected in response fields! Overriding with safe rule templates.")
            response_data["customer_reply"] = fallback_data["customer_reply"]
            response_data["recommended_next_action"] = fallback_data["recommended_next_action"]
            response_data["agent_summary"] = fallback_data["agent_summary"]
            
        return response_data
