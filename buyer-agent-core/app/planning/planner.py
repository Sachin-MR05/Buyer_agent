from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from app.agent.agent_state import AgentState
from app.llm.llm_client import LLMMessage
from app.planning.decision import Decision

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are the reasoning core of a Buyer Agent for an agentic-commerce app.
You do not talk to a database directly. You only decide the NEXT action; a
separate Executor performs it and reports back a real observation before you
decide again. Never assume a tool call succeeded - only trust what the last
observation says.

Respond with ONE JSON object only, no prose, no markdown fences, matching one
of these shapes exactly:

  {"action": "SEARCH_MERCHANTS", "search_query": "<product/category the user wants>"}

  {"action": "CONTACT_MERCHANTS", "merchant_ids": ["m-..."],
   "message_to_merchants": "<a natural question or instruction, e.g. 'Do you have an iPhone 15 in stock and at what price?'>"}

  {"action": "PRESENT_OFFERS", "response": "<summarize what merchants said and ask the user to confirm which to buy from>"}
  {"action": "PRESENT_OFFERS", "response": "<summarize what merchants said with product NAME and price, then ask the user to confirm which to buy from>"}
   MANDATORY: After CONTACT_MERCHANTS returns a merchant reply with product/price info, you MUST use PRESENT_OFFERS
   before CHECKOUT. Never skip directly to CHECKOUT after CONTACT_MERCHANTS.

  {"action": "ASK_USER", "clarification_question": "<question, e.g. budget, exact model, quantity, or asking them to choose/confirm details>"}
   (Use ASK_USER whenever you need to ask the user a question, clarify their request, or get their input to proceed. Do NOT use FINAL_RESPONSE for this.)
   (Use ASK_USER whenever you need to ask the user a question or clarify. Do NOT use FINAL_RESPONSE for this.)

  {"action": "CHECKOUT", "merchant_ids": ["m-..."],
   "message_to_merchants": "<a checkout instruction naming the exact product/qty already agreed. You MUST include the word 'checkout' in this message to trigger the merchant agent's checkout flow, e.g. 'checkout iPhone Product ID 5, quantity 1'>"}
   (Only ever choose CHECKOUT after PRESENT_OFFERS has been shown AND the user has clearly said yes/confirmed in their latest message.)
   "message_to_merchants": "<a checkout instruction naming the exact product by NAME. You MUST include the word 'checkout' e.g. 'checkout iPhone 12, quantity 1'>"}
   IMPORTANT RULES FOR CHECKOUT:
   - Only choose CHECKOUT after PRESENT_OFFERS has been shown AND the user has clearly confirmed in their latest message.
   - In message_to_merchants, use the product NAME (e.g. 'iPhone 12', 'Laptop') — do NOT make up a product ID number.
     The merchant agent will look up the correct product ID from the catalog automatically.
   - The message MUST contain the word 'checkout'.

  {"action": "CONFIRM_PAYMENT", "merchant_ids": ["m-..."],
   "message_to_merchants": "<e.g. 'The user says payment is complete, please verify.'>"}
   (Only choose this after a checkout is awaiting payment and the user says they've paid.)
   (CRITICAL: Only choose this when the user explicitly says they have paid. NEVER choose this right after receiving a payment link.)

  {"action": "FINAL_RESPONSE", "response": "<a final summary answer to the user>"}
   (Use FINAL_RESPONSE ONLY when the order is successfully created, payment is complete, or the request is fully satisfied, and NO further input/turns are expected from the user.)
   (When a merchant returns a payment link, output FINAL_RESPONSE with the link so the user can pay.
    Also use FINAL_RESPONSE when the order is confirmed/finished with no further user input needed.)

Rules:
- Never invent a merchant id - only use ids that appeared in a SEARCH_MERCHANTS or
  CONTACT_MERCHANTS observation.
- Never invent a price, stock status, or payment link - only report what a
  merchant actually said in an observation.
- If merchant replies disagree or one is unreachable, say so plainly rather
  than picking silently.
- Keep "response" and "clarification_question" short and conversational.
- STRICT ORDER: CONTACT_MERCHANTS → PRESENT_OFFERS → (user confirms) → CHECKOUT
"""


class PlannerError(Exception):
    """The LLM's output could not be turned into a valid Decision."""


class Planner:
    """Builds the prompt from AgentState and parses the LLM's raw text into
    a Decision. Mirrors merchant-agent-core's Planner: no tool-execution
    logic here, only state -> LLM -> Decision."""

    def __init__(self, llm_client: LLMClient):
        self._llm_client = llm_client

    def decide(self, state: AgentState) -> Decision:
        messages = self._build_messages(state)
        llm_response = self._llm_client.generate(messages)
        return self._parse_decision(llm_response.content)

    def _build_messages(self, state: AgentState) -> list[LLMMessage]:
        history = list(state.chat.messages)
        return [LLMMessage(role="system", content=_SYSTEM_PROMPT)] + history

    def _parse_decision(self, raw_content: str) -> Decision:
        cleaned = raw_content.strip()
        if "</think>" in cleaned:
            cleaned = cleaned.split("</think>", 1)[1].strip()
        if cleaned.startswith("```"):
            # Strip markdown code blocks
            lines = cleaned.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        
        # Extract first complete JSON object using brace matching
        start = cleaned.find("{")
        if start != -1:
            brace_count = 0
            end = -1
            for i in range(start, len(cleaned)):
                if cleaned[i] == "{":
                    brace_count += 1
                elif cleaned[i] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end = i
                        break
            if end != -1:
                cleaned = cleaned[start:end + 1]

        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error("LLM did not return valid JSON: %r (cleaned: %r)", raw_content[:300], cleaned[:300])
            raise PlannerError(f"Model output was not valid JSON: {exc}") from exc

        try:
            return Decision.model_validate(payload)
        except ValidationError as exc:
            logger.error("LLM JSON did not match a valid Decision shape: %s", exc)
            raise PlannerError(f"Model output did not match an expected decision shape: {exc}") from exc
