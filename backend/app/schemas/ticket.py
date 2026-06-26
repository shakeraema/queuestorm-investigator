from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field

# Input Enums
LanguageType = Literal["en", "bn", "mixed"]
ChannelType = Literal["in_app_chat", "call_center", "email", "merchant_portal", "field_agent"]
UserType = Literal["customer", "merchant", "agent", "unknown"]
TransactionType = Literal["transfer", "payment", "cash_in", "cash_out", "settlement", "refund"]
TransactionStatus = Literal["completed", "failed", "pending", "reversed"]

# Output Enums
EvidenceVerdictType = Literal["consistent", "inconsistent", "insufficient_data"]
CaseType = Literal[
    "wrong_transfer",
    "payment_failed",
    "refund_request",
    "duplicate_payment",
    "merchant_settlement_delay",
    "agent_cash_in_issue",
    "phishing_or_social_engineering",
    "other"
]
SeverityType = Literal["low", "medium", "high", "critical"]
DepartmentType = Literal[
    "customer_support",
    "dispute_resolution",
    "payments_ops",
    "merchant_operations",
    "agent_operations",
    "fraud_risk"
]

class TransactionHistoryEntry(BaseModel):
    transaction_id: str = Field(..., description="Unique transaction identifier")
    timestamp: str = Field(..., description="ISO 8601 timestamp when transaction occurred")
    type: TransactionType = Field(..., description="Type of transaction")
    amount: float = Field(..., description="Amount in BDT")
    counterparty: str = Field(..., description="Recipient phone number, merchant ID, or agent ID")
    status: TransactionStatus = Field(..., description="Transaction status")

class TicketAnalysisRequest(BaseModel):
    ticket_id: str = Field(..., description="Unique ticket identifier")
    complaint: str = Field(..., description="Customer complaint text in English, Bangla, or mixed Banglish")
    language: Optional[LanguageType] = None
    channel: Optional[ChannelType] = None
    user_type: Optional[UserType] = None
    campaign_context: Optional[str] = None
    transaction_history: Optional[List[TransactionHistoryEntry]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None

class TicketAnalysisResponse(BaseModel):
    ticket_id: str = Field(..., description="Unique ticket identifier. Must match request.")
    relevant_transaction_id: Optional[str] = Field(..., description="Transaction ID the complaint refers to, or null")
    evidence_verdict: EvidenceVerdictType = Field(..., description="Verdict based on transaction evidence")
    case_type: CaseType = Field(..., description="Classification category from the taxonomy")
    severity: SeverityType = Field(..., description="Assigned severity level")
    department: DepartmentType = Field(..., description="Department routing for the case")
    agent_summary: str = Field(..., description="Concise agent ready summary of the case")
    recommended_next_action: str = Field(..., description="Suggested next step for the support agent")
    customer_reply: str = Field(..., description="Safe official reply that respects all safety rules")
    human_review_required: bool = Field(..., description="Whether this case requires human escalation")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Float between 0 and 1")
    reason_codes: Optional[List[str]] = Field(default_factory=list, description="Reason labels supporting the decision")
