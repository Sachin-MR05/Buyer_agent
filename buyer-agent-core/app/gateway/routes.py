from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.agent.agent_state import ChatState
from app.agent.buyer_agent import BuyerAgent
from app.registry.models import MerchantEntryPublic, MerchantManifest
from app.registry.service import RegistryService, RegistryValidationError

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Dependency providers - overridden by main.py's dependency_overrides, same
# pattern as merchant-agent-core/app/gateway/routes.py.
# ---------------------------------------------------------------------------
def get_buyer_agent() -> BuyerAgent:
    raise NotImplementedError("BuyerAgent dependency was not configured")


def get_registry_service() -> RegistryService:
    raise NotImplementedError("RegistryService dependency was not configured")


# ---------------------------------------------------------------------------
# Chat - separate from the registry entirely, as requested: this endpoint
# never returns registry management data, and the registry endpoints below
# never return conversation history.
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    chat_id: str | None = Field(default=None, alias="chatId")
    message: str

    model_config = ConfigDict(populate_by_name=True)


class MerchantThreadView(BaseModel):
    merchant_id: str = Field(alias="merchantId")
    shop_name: str = Field(alias="shopName")
    transcript: list[dict]

    model_config = ConfigDict(populate_by_name=True)


class ChatMessageView(BaseModel):
    role: str
    text: str


class ChatResponse(BaseModel):
    chat_id: str = Field(alias="chatId")
    status: str
    message: str
    messages: list[ChatMessageView]
    merchant_threads: list[MerchantThreadView] = Field(alias="merchantThreads")

    model_config = ConfigDict(populate_by_name=True)


class ChatSummary(BaseModel):
    chat_id: str = Field(alias="chatId")
    title: str | None

    model_config = ConfigDict(populate_by_name=True)


class ChatRenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


@router.post("/buyer/chat", response_model=ChatResponse, response_model_by_alias=True)
def post_chat(
    request: ChatRequest,
    buyer_agent: BuyerAgent = Depends(get_buyer_agent),
):
    # TODO: replace this hardcoded user id with the authenticated user from
    # your existing session/JWT once the Buyer Agent sits behind real auth.
    user_id = "1"

    state = buyer_agent.run(user_message=request.message, user_id=user_id, chat_id=request.chat_id)

    threads = [
        MerchantThreadView(merchantId=t.merchant_id, shopName=t.shop_name, transcript=t.transcript)
        for t in state.chat.merchant_threads.values()
    ]
    visible_messages = [
        ChatMessageView(role=m.role, text=m.content) for m in state.chat.messages if m.role in ("user", "assistant")
    ]
    return ChatResponse(
        chatId=state.chat.chat_id,
        status=state.status.value,
        message=state.final_response or state.error or "",
        messages=visible_messages,
        merchantThreads=threads,
    )


@router.get("/buyer/chats", response_model=list[ChatSummary], response_model_by_alias=True)
def list_chats(buyer_agent: BuyerAgent = Depends(get_buyer_agent)):
    return [ChatSummary(chatId=c.chat_id, title=c.title) for c in buyer_agent.list_chats()]


@router.get("/buyer/chats/{chat_id}", response_model=ChatResponse, response_model_by_alias=True)
def get_chat(chat_id: str, buyer_agent: BuyerAgent = Depends(get_buyer_agent)):
    chat: ChatState | None = buyer_agent.get_chat(chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    threads = [
        MerchantThreadView(merchantId=t.merchant_id, shopName=t.shop_name, transcript=t.transcript)
        for t in chat.merchant_threads.values()
    ]
    visible_messages = [ChatMessageView(role=m.role, text=m.content) for m in chat.messages if m.role in ("user", "assistant")]
    last_text = chat.messages[-1].content if chat.messages else ""
    return ChatResponse(
        chatId=chat.chat_id, status="LOADED", message=last_text, messages=visible_messages, merchantThreads=threads
    )


@router.patch("/buyer/chats/{chat_id}", response_model=ChatSummary, response_model_by_alias=True)
def rename_chat(chat_id: str, request: ChatRenameRequest, buyer_agent: BuyerAgent = Depends(get_buyer_agent)):
    title = request.title.strip()
    if not title or not buyer_agent.rename_chat(chat_id, title):
        raise HTTPException(status_code=404, detail="Chat not found")
    return ChatSummary(chatId=chat_id, title=title)


@router.delete("/buyer/chats/{chat_id}", status_code=204)
def delete_chat(chat_id: str, buyer_agent: BuyerAgent = Depends(get_buyer_agent)):
    if not buyer_agent.delete_chat(chat_id):
        raise HTTPException(status_code=404, detail="Chat not found")


# ---------------------------------------------------------------------------
# Registry - completely separate from chat. Add-merchant accepts the exact
# manifest JSON a shop's AgentInfo page hands out, for a single paste.
# Never returns the auth token, encrypted or otherwise, once saved.
# ---------------------------------------------------------------------------
@router.post("/registry", response_model=MerchantEntryPublic, response_model_by_alias=True)
def add_merchant(manifest: MerchantManifest, registry: RegistryService = Depends(get_registry_service)):
    try:
        return registry.add(manifest)
    except RegistryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/registry", response_model=list[MerchantEntryPublic], response_model_by_alias=True)
def list_merchants(registry: RegistryService = Depends(get_registry_service)):
    return registry.list()


@router.delete("/registry/{merchant_id}", status_code=204)
def delete_merchant(merchant_id: str, registry: RegistryService = Depends(get_registry_service)):
    if not registry.delete(merchant_id):
        raise HTTPException(status_code=404, detail="Merchant not found")


@router.get("/health")
def health():
    return {"status": "UP"}
