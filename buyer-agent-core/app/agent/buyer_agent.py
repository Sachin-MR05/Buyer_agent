from __future__ import annotations

import logging
import uuid
from typing import Optional

from app.agent.agent_loop import AgentLoop
from app.agent.agent_state import AgentState, ChatState
from app.execution.executor import Executor
from app.llm.llm_client import LLMClient, LLMUnavailableError
from app.persistence.chat_store import ChatStore, ChatSummary
from app.planning.planner import Planner
from app.registry.service import RegistryService
from app.tools.merchant_client import MerchantClient
from app.tools.registry_tool import RegistryTool

logger = logging.getLogger(__name__)


class BuyerAgent:
    """High-level entry point, composed once at startup (see gateway/wiring.py)
    and reused across requests. Chat-level state (ChatState) is persisted
    via ChatStore (Postgres) rather than held in memory - so, unlike the
    merchant repo's current in-memory `_session_history`, a chat survives a
    process restart."""

    def __init__(
        self,
        llm_client: LLMClient,
        registry_tool: RegistryTool,
        registry_service: RegistryService,
        merchant_client: MerchantClient,
        chat_store: ChatStore,
        max_iterations: int = 8,
        max_merchants_per_query: int = 4,
    ):
        self._planner = Planner(llm_client)
        self._executor = Executor(registry_tool, registry_service, merchant_client, max_merchants_per_query)
        self._agent_loop = AgentLoop(self._planner, self._executor, max_iterations)
        self._chat_store = chat_store

    def list_chats(self) -> list[ChatSummary]:
        return self._chat_store.list_summaries()

    def get_chat(self, chat_id: str) -> Optional[ChatState]:
        return self._chat_store.get(chat_id)

    def rename_chat(self, chat_id: str, title: str) -> bool:
        return self._chat_store.rename(chat_id, title)

    def delete_chat(self, chat_id: str) -> bool:
        return self._chat_store.delete(chat_id)

    def run(self, user_message: str, user_id: str, chat_id: Optional[str] = None) -> AgentState:
        chat_id = chat_id or f"chat-{uuid.uuid4().hex[:10]}"
        chat = self._chat_store.get(chat_id) or ChatState(chat_id=chat_id, user_id=user_id)
        if chat.title is None:
            chat.title = user_message[:60]

        state = AgentState.create(chat=chat, user_message=user_message)
        state.add_message("user", user_message)

        logger.info("Buyer agent run started chat=%s", chat_id)
        try:
            result_state = self._agent_loop.run(state)
        except LLMUnavailableError as exc:
            logger.error("LLM provider unavailable for chat %s: %s", chat_id, exc)
            state.fail("The assistant is temporarily unavailable. Please try again shortly.")
            result_state = state

        self._chat_store.save(result_state.chat)
        return result_state
