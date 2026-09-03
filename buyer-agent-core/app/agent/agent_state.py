from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from app.llm.llm_client import LLMMessage
from app.tools.merchant_client import MerchantReply


class AgentStatus(str, Enum):
    INITIALIZED = "INITIALIZED"
    THINKING = "THINKING"
    ACTING = "ACTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    WAITING_FOR_USER = "WAITING_FOR_USER"


class TransactionStatus(str, Enum):
    NONE = "NONE"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    PAID_CLAIMED = "PAID_CLAIMED"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


@dataclass
class MerchantThread:
    """One merchant's own continuous conversation with the Buyer Agent.
    merchant_session_id is generated once and reused for every message to
    that merchant, so the merchant's own AgentState treats it as one
    ongoing session rather than a fresh one each turn."""

    merchant_id: str
    shop_name: str
    merchant_session_id: str
    transcript: list[dict[str, Any]] = field(default_factory=list)
    last_status: Optional[str] = None

    def record(self, direction: str, text: str, status: Optional[str] = None) -> None:
        self.transcript.append(
            {"direction": direction, "text": text, "status": status, "ts": datetime.now(timezone.utc).isoformat()}
        )
        if status:
            self.last_status = status


@dataclass
class CandidateOffer:
    merchant_id: str
    shop_name: str
    summary: str
    raw_message: str


@dataclass
class ChatState:
    """Cross-turn state for one buyer chat session - the equivalent of
    MerchantAgent's per-session_id history, but richer, since the Buyer
    Agent has to remember which shops it's already talked to and what
    they've offered."""

    chat_id: str
    user_id: str
    title: Optional[str] = None
    messages: list[LLMMessage] = field(default_factory=list)
    merchant_threads: dict[str, MerchantThread] = field(default_factory=dict)
    candidate_offers: list[CandidateOffer] = field(default_factory=list)
    awaiting_confirmation: bool = False
    selected_merchant_id: Optional[str] = None
    transaction_status: TransactionStatus = TransactionStatus.NONE
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def thread_for(self, merchant_id: str, shop_name: str) -> MerchantThread:
        if merchant_id not in self.merchant_threads:
            self.merchant_threads[merchant_id] = MerchantThread(
                merchant_id=merchant_id,
                shop_name=shop_name,
                merchant_session_id=f"buyer-sess-{uuid.uuid4().hex[:10]}",
            )
        return self.merchant_threads[merchant_id]


@dataclass
class AgentState:
    """Explicit, self-contained state for a single Buyer Agent run (one
    user message -> one or more loop iterations -> one terminal status).
    Mirrors merchant-agent-core/app/agent/agent_state.py."""

    chat: ChatState
    user_message: str
    request_id: Optional[str] = None

    iteration: int = 0
    status: AgentStatus = AgentStatus.INITIALIZED
    final_response: Optional[str] = None
    error: Optional[str] = None

    last_merchant_replies: list[MerchantReply] = field(default_factory=list)

    @staticmethod
    def create(chat: ChatState, user_message: str, request_id: Optional[str] = None) -> "AgentState":
        return AgentState(chat=chat, user_message=user_message, request_id=request_id)

    def add_message(self, role: str, content: str) -> None:
        self.chat.messages.append(LLMMessage(role=role, content=content))

    def increment_iteration(self) -> int:
        self.iteration += 1
        return self.iteration

    def complete(self, response: str) -> None:
        self.final_response = response
        self.status = AgentStatus.COMPLETED

    def fail(self, error_message: str) -> None:
        self.error = error_message
        self.final_response = error_message
        self.add_message("assistant", error_message)
        self.status = AgentStatus.FAILED

    def wait_for_user(self, message: str) -> None:
        self.final_response = message
        self.status = AgentStatus.WAITING_FOR_USER
