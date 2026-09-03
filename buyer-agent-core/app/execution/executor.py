from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.agent.agent_state import AgentState, TransactionStatus
from app.planning.decision import Decision, DecisionAction
from app.registry.service import RegistryService
from app.tools.merchant_client import MerchantClient, MerchantClientError
from app.tools.registry_tool import RegistryTool

logger = logging.getLogger(__name__)


class ExecutorError(Exception):
    """Base error executing a Decision."""


class CheckoutNotAuthorizedError(ExecutorError):
    """A CHECKOUT decision arrived without the user ever having been shown
    (and having had the chance to respond to) a PRESENT_OFFERS step in
    this chat. This is the single, deterministic gate - see class
    docstring on Executor - the LLM can *decide* to check out, but it can
    never skip having asked first."""


class PaymentConfirmationNotExpectedError(ExecutorError):
    """A CONFIRM_PAYMENT decision arrived while no checkout is actually
    awaiting payment."""


@dataclass
class ObservationResult:
    """What the Executor hands back to the loop after acting - always
    turned into a 'tool' message so the next Planner iteration sees it as
    real information, never assumed."""

    text: str


class Executor:
    """Runs a single Decision against real tools (registry search, or an
    HTTP call to one or more merchant agents).

    Mirrors merchant-agent-core's Executor: this is the ONLY place with an
    enforced authorization checkpoint (authorization_check() there,
    _require_checkout_authorized() here) - a single named call site, not a
    scattered inline check, so a future Approval Gate / spend-limit policy
    has exactly one place to plug into.
    """

    def __init__(
        self,
        registry_tool: RegistryTool,
        registry_service: RegistryService,
        merchant_client: MerchantClient,
        max_merchants_per_query: int,
    ):
        self._registry_tool = registry_tool
        self._registry_service = registry_service
        self._merchant_client = merchant_client
        self._max_merchants_per_query = max_merchants_per_query

    def execute(self, decision: Decision, state: AgentState) -> ObservationResult:
        if decision.action == DecisionAction.SEARCH_MERCHANTS:
            return self._search_merchants(decision, state)

        if decision.action == DecisionAction.CONTACT_MERCHANTS:
            return self._contact_merchants(decision, state)

        if decision.action == DecisionAction.CHECKOUT:
            self._require_checkout_authorized(state)
            return self._checkout(decision, state)

        if decision.action == DecisionAction.CONFIRM_PAYMENT:
            self._require_payment_expected(state)
            return self._confirm_payment(decision, state)

        raise ExecutorError(f"Executor cannot act on decision action {decision.action}")

    # ------------------------------------------------------------------
    # Authorization checkpoints
    # ------------------------------------------------------------------

    def _require_checkout_authorized(self, state: AgentState) -> None:
        """The single fixed checkout gate. state.chat.awaiting_confirmation
        is only ever set True by a prior PRESENT_OFFERS step, and is
        cleared the moment checkout proceeds - so the LLM cannot reach
        CHECKOUT without the user having first been shown offers and given
        a real turn to respond in between."""
        if not state.chat.awaiting_confirmation:
            raise CheckoutNotAuthorizedError(
                "Checkout requires the user to have been presented offers and to have replied first."
            )

    def _require_payment_expected(self, state: AgentState) -> None:
        if state.chat.transaction_status != TransactionStatus.AWAITING_PAYMENT:
            raise PaymentConfirmationNotExpectedError(
                "No checkout is currently awaiting payment confirmation for this chat."
            )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _search_merchants(self, decision: Decision, state: AgentState) -> ObservationResult:
        matches = self._registry_tool.search(decision.search_query, self._max_merchants_per_query)
        if not matches:
            return ObservationResult("No merchants are registered yet. Ask the user to add one in the registry.")
        lines = [f"- id={m.id} | {m.shop_name}: {m.description}" for m in matches]
        return ObservationResult("Relevant registered merchants:\n" + "\n".join(lines))

    def _contact_merchants(self, decision: Decision, state: AgentState) -> ObservationResult:
        merchants = self._registry_service.get_many_public(decision.merchant_ids)
        if not merchants:
            return ObservationResult("None of the requested merchant ids exist in the registry.")

        session_ids = {
            m.id: state.chat.thread_for(m.id, m.shop_name).merchant_session_id for m in merchants
        }
        for m in merchants:
            state.chat.thread_for(m.id, m.shop_name).record("sent", decision.message_to_merchants)

        replies = self._merchant_client.send_to_many(
            merchants, buyer_user_id=state.chat.user_id, session_ids=session_ids, message=decision.message_to_merchants
        )
        state.last_merchant_replies = replies

        lines = []
        for reply in replies:
            thread = state.chat.thread_for(reply.merchant_id, reply.shop_name)
            if reply.status == "FAILED" and not reply.message:
                thread.record("received", reply.error or "unreachable", status=reply.status)
                lines.append(f"- {reply.shop_name}: UNREACHABLE ({reply.error})")
            else:
                thread.record("received", reply.message, status=reply.status)
                lines.append(f"- {reply.shop_name} [{reply.status}]: {reply.message}")

        return ObservationResult("Merchant replies:\n" + "\n".join(lines))

    def _checkout(self, decision: Decision, state: AgentState) -> ObservationResult:
        merchants = self._registry_service.get_many_public(decision.merchant_ids)
        if not merchants:
            return ObservationResult("The selected merchant no longer exists in the registry.")
        merchant = merchants[0]

        state.chat.awaiting_confirmation = False
        state.chat.selected_merchant_id = merchant.id

        thread = state.chat.thread_for(merchant.id, merchant.shop_name)
        thread.record("sent", decision.message_to_merchants)
        try:
            reply = self._merchant_client.send(
                merchant, buyer_user_id=state.chat.user_id, session_id=thread.merchant_session_id,
                message=decision.message_to_merchants,
            )
        except MerchantClientError as exc:
            state.chat.transaction_status = TransactionStatus.FAILED
            return ObservationResult(f"Checkout failed - could not reach {merchant.shop_name}: {exc}")

        thread.record("received", reply.message, status=reply.status)
        state.last_merchant_replies = [reply]

        if reply.status in ("SUCCESS", "WAITING_FOR_CONFIRMATION", "WAITING_FOR_INPUT"):
            state.chat.transaction_status = TransactionStatus.AWAITING_PAYMENT
        else:
            state.chat.transaction_status = TransactionStatus.FAILED

        data_note = f" (data: {reply.data})" if reply.data else ""
        return ObservationResult(f"{merchant.shop_name} checkout response [{reply.status}]: {reply.message}{data_note}")

    def _confirm_payment(self, decision: Decision, state: AgentState) -> ObservationResult:
        merchants = self._registry_service.get_many_public(decision.merchant_ids)
        if not merchants:
            return ObservationResult("The selected merchant no longer exists in the registry.")
        merchant = merchants[0]

        state.chat.transaction_status = TransactionStatus.PAID_CLAIMED
        thread = state.chat.thread_for(merchant.id, merchant.shop_name)
        thread.record("sent", decision.message_to_merchants)
        try:
            reply = self._merchant_client.send(
                merchant, buyer_user_id=state.chat.user_id, session_id=thread.merchant_session_id,
                message=decision.message_to_merchants,
            )
        except MerchantClientError as exc:
            state.chat.transaction_status = TransactionStatus.FAILED
            return ObservationResult(f"Could not verify payment with {merchant.shop_name}: {exc}")

        thread.record("received", reply.message, status=reply.status)
        state.last_merchant_replies = [reply]
        state.chat.transaction_status = (
            TransactionStatus.CONFIRMED if reply.status == "SUCCESS" else TransactionStatus.FAILED
        )
        return ObservationResult(f"{merchant.shop_name} payment verification [{reply.status}]: {reply.message}")
