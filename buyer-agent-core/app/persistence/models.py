from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.persistence.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MerchantRow(Base):
    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    shop_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    agent_url: Mapped[str] = mapped_column(String(500), nullable=False)
    # Fernet ciphertext only - see app/registry/crypto.py. Never plaintext.
    auth_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ChatRow(Base):
    __tablename__ = "chats"

    chat_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    awaiting_confirmation: Mapped[bool] = mapped_column(default=False)
    selected_merchant_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    transaction_status: Mapped[str] = mapped_column(String(30), default="NONE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    messages: Mapped[list["MessageRow"]] = relationship(
        back_populates="chat", cascade="all, delete-orphan", order_by="MessageRow.id"
    )
    threads: Mapped[list["MerchantThreadRow"]] = relationship(
        back_populates="chat", cascade="all, delete-orphan"
    )


class MessageRow(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.chat_id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant | tool
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    chat: Mapped["ChatRow"] = relationship(back_populates="messages")


class MerchantThreadRow(Base):
    __tablename__ = "merchant_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[str] = mapped_column(ForeignKey("chats.chat_id", ondelete="CASCADE"), index=True)
    merchant_id: Mapped[str] = mapped_column(String(40), nullable=False)
    shop_name: Mapped[str] = mapped_column(String(200), nullable=False)
    merchant_session_id: Mapped[str] = mapped_column(String(60), nullable=False)
    last_status: Mapped[str | None] = mapped_column(String(40), nullable=True)

    chat: Mapped["ChatRow"] = relationship(back_populates="threads")
    lines: Mapped[list["TranscriptLineRow"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan", order_by="TranscriptLineRow.id"
    )


class TranscriptLineRow(Base):
    __tablename__ = "transcript_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("merchant_threads.id", ondelete="CASCADE"), index=True)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # sent | received
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    thread: Mapped["MerchantThreadRow"] = relationship(back_populates="lines")
