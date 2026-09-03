from __future__ import annotations

import logging

from app.agent.agent_state import AgentState, AgentStatus
from app.execution.executor import CheckoutNotAuthorizedError, Executor, ExecutorError
from app.planning.decision import DecisionAction
from app.planning.planner import Planner, PlannerError

logger = logging.getLogger(__name__)


class AgentLoop:
    """The core think -> act -> observe loop. Identical shape to
    merchant-agent-core/app/agent/agent_loop.py: the LLM decides the next
    action every iteration; the loop never assumes a fixed sequence of
    searches/contacts/checkout."""

    def __init__(self, planner: Planner, executor: Executor, max_iterations: int):
        self._planner = planner
        self._executor = executor
        self._max_iterations = max_iterations

    def run(self, state: AgentState) -> AgentState:
        logger.info("Buyer agent loop started for chat %s", state.chat.chat_id)

        while True:
            iteration = state.increment_iteration()
            if iteration > self._max_iterations:
                logger.warning("Chat %s exceeded max iterations (%d)", state.chat.chat_id, self._max_iterations)
                state.fail(
                    "I wasn't able to finish this within the allowed number of steps. "
                    "Please try rephrasing or narrowing your request."
                )
                return state

            state.status = AgentStatus.THINKING
            try:
                decision = self._planner.decide(state)
            except PlannerError as exc:
                logger.error("Chat %s - planning failed: %s", state.chat.chat_id, exc)
                state.fail("I couldn't determine the next step for this request. Please try again.")
                return state

            if decision.action == DecisionAction.FINAL_RESPONSE:
                state.add_message("assistant", decision.response)
                state.complete(decision.response)
                return state

            if decision.action == DecisionAction.ASK_USER:
                state.add_message("assistant", decision.clarification_question)
                state.wait_for_user(decision.clarification_question)
                return state

            if decision.action == DecisionAction.PRESENT_OFFERS:
                state.chat.awaiting_confirmation = True
                state.add_message("assistant", decision.response)
                state.wait_for_user(decision.response)
                return state

            state.status = AgentStatus.ACTING
            try:
                observation = self._executor.execute(decision, state)
            except CheckoutNotAuthorizedError as exc:
                logger.warning("Chat %s - blocked unauthorized checkout: %s", state.chat.chat_id, exc)
                # Deliberately not a hard failure: tell the LLM why, as an
                # observation, so it can recover (e.g. go back to
                # PRESENT_OFFERS) instead of the whole turn erroring out.
                state.add_message("tool", f"Checkout was blocked: {exc}")
                continue
            except ExecutorError as exc:
                logger.error("Chat %s - execution failed: %s", state.chat.chat_id, exc)
                state.fail(f"Something went wrong while acting on that: {exc}")
                return state

            state.add_message("tool", observation.text)
            # Loop again - the LLM sees the observation and decides next.
