from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class DecisionAction(str, Enum):
    SEARCH_MERCHANTS = "SEARCH_MERCHANTS"     # look up relevant shops in the registry (local)
    CONTACT_MERCHANTS = "CONTACT_MERCHANTS"   # ask one or more shops a question
    PRESENT_OFFERS = "PRESENT_OFFERS"         # summarize findings, pause for the user's go-ahead
    ASK_USER = "ASK_USER"                     # need clarification (budget, model, quantity...)
    CHECKOUT = "CHECKOUT"                     # gated - only runs after the user said yes
    CONFIRM_PAYMENT = "CONFIRM_PAYMENT"       # user says they paid - ask the merchant to verify
    FINAL_RESPONSE = "FINAL_RESPONSE"         # done for this turn


class Decision(BaseModel):
    """The structured decision the Planner extracts from the LLM's output
    for a single iteration of the Buyer Agent loop. Mirrors
    merchant-agent-core/app/planning/decision.py - the LLM decides *what*,
    the Executor enforces *whether it's allowed* (see the checkout gate)."""

    action: DecisionAction

    # SEARCH_MERCHANTS
    search_query: Optional[str] = None

    # CONTACT_MERCHANTS / CHECKOUT / CONFIRM_PAYMENT
    merchant_ids: list[str] = Field(default_factory=list)
    message_to_merchants: Optional[str] = None

    # PRESENT_OFFERS / FINAL_RESPONSE / ASK_USER
    response: Optional[str] = None
    clarification_question: Optional[str] = None

    rationale: Optional[str] = None

    @model_validator(mode="after")
    def _validate_shape_matches_action(self) -> "Decision":
        if self.action == DecisionAction.SEARCH_MERCHANTS and not self.search_query:
            raise ValueError("SEARCH_MERCHANTS requires search_query")
        if self.action in (DecisionAction.CONTACT_MERCHANTS, DecisionAction.CHECKOUT, DecisionAction.CONFIRM_PAYMENT):
            if not self.merchant_ids or not self.message_to_merchants:
                raise ValueError(f"{self.action.value} requires merchant_ids and message_to_merchants")
        if self.action == DecisionAction.PRESENT_OFFERS and not self.response:
            raise ValueError("PRESENT_OFFERS requires response")
        if self.action == DecisionAction.ASK_USER and not self.clarification_question:
            raise ValueError("ASK_USER requires clarification_question")
        if self.action == DecisionAction.FINAL_RESPONSE and not self.response:
            raise ValueError("FINAL_RESPONSE requires response")
        return self
