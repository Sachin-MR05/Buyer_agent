from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload, sessionmaker

from app.agent.agent_state import ChatState, MerchantThread, TransactionStatus
from app.llm.llm_client import LLMMessage
from app.persistence.db import session_scope
from app.persistence.models import ChatRow, MerchantThreadRow, MessageRow, TranscriptLineRow


class ChatSummary:
    def __init__(self, chat_id: str, title: Optional[str]):
        self.chat_id = chat_id
        self.title = title


class ChatStore:
    """Persists ChatState (messages, per-merchant threads/transcripts,
    confirmation/transaction flags) in Postgres.

    Replaces BuyerAgent's previous in-memory `_chats` dict - same
    limitation MerchantAgent's own `_session_history` currently has on the
    merchant side, now fixed on this side. Saves are a simple
    delete-and-reinsert of a chat's messages/threads each time (chats here
    are small - a handful of turns and shops - so this stays fast and
    avoids diffing logic entirely).
    """

    def __init__(self, session_factory: sessionmaker):
        self._session_factory = session_factory

    def get(self, chat_id: str) -> Optional[ChatState]:
        with session_scope(self._session_factory) as session:
            row = session.scalars(
                select(ChatRow)
                .where(ChatRow.chat_id == chat_id)
                .options(selectinload(ChatRow.messages), selectinload(ChatRow.threads).selectinload(MerchantThreadRow.lines))
            ).first()
            return _to_chat_state(row) if row else None

    def list_summaries(self) -> list[ChatSummary]:
        with session_scope(self._session_factory) as session:
            rows = session.scalars(select(ChatRow).order_by(ChatRow.created_at.desc())).all()
            return [ChatSummary(chat_id=r.chat_id, title=r.title) for r in rows]

    def rename(self, chat_id: str, title: str) -> bool:
        with session_scope(self._session_factory) as session:
            row = session.get(ChatRow, chat_id)
            if row is None:
                return False
            row.title = title
            return True

    def delete(self, chat_id: str) -> bool:
        with session_scope(self._session_factory) as session:
            row = session.get(ChatRow, chat_id)
            if row is None:
                return False
            session.delete(row)
            return True

    def save(self, chat: ChatState) -> None:
        with session_scope(self._session_factory) as session:
            row = session.get(ChatRow, chat.chat_id)
            if row is None:
                row = ChatRow(chat_id=chat.chat_id, user_id=chat.user_id, created_at=chat.created_at)
                session.add(row)

            row.title = chat.title
            row.awaiting_confirmation = chat.awaiting_confirmation
            row.selected_merchant_id = chat.selected_merchant_id
            row.transaction_status = chat.transaction_status.value

            # Simplest correct approach at this scale: replace children
            # wholesale rather than diff them.
            row.messages.clear()
            for m in chat.messages:
                row.messages.append(MessageRow(role=m.role, content=m.content))

            row.threads.clear()
            session.flush()  # let cascade deletes apply before re-adding
            for thread in chat.merchant_threads.values():
                thread_row = MerchantThreadRow(
                    merchant_id=thread.merchant_id,
                    shop_name=thread.shop_name,
                    merchant_session_id=thread.merchant_session_id,
                    last_status=thread.last_status,
                )
                for line in thread.transcript:
                    thread_row.lines.append(
                        TranscriptLineRow(direction=line["direction"], text=line["text"], status=line.get("status"))
                    )
                row.threads.append(thread_row)


def _to_chat_state(row: ChatRow) -> ChatState:
    chat = ChatState(
        chat_id=row.chat_id,
        user_id=row.user_id,
        title=row.title,
        messages=[LLMMessage(role=m.role, content=m.content) for m in row.messages],
        awaiting_confirmation=row.awaiting_confirmation,
        selected_merchant_id=row.selected_merchant_id,
        transaction_status=TransactionStatus(row.transaction_status),
        created_at=row.created_at,
    )
    for thread_row in row.threads:
        thread = MerchantThread(
            merchant_id=thread_row.merchant_id,
            shop_name=thread_row.shop_name,
            merchant_session_id=thread_row.merchant_session_id,
            last_status=thread_row.last_status,
        )
        thread.transcript = [
            {"direction": line.direction, "text": line.text, "status": line.status, "ts": line.ts.isoformat()}
            for line in thread_row.lines
        ]
        chat.merchant_threads[thread.merchant_id] = thread
    return chat
