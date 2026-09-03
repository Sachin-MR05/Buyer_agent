"""Not a pytest unit test - a standalone script proving the real end-to-end
flow: registry -> search -> contact merchant (real HTTP, in a thread) ->
present offers -> user confirms -> checkout -> user says paid -> confirm.

Run with: python tests/smoke_full_flow.py
"""
from __future__ import annotations

import json
import threading
import time

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.gateway.wiring import build_app
from app.llm.llm_client import LLMClient, LLMResponse


# ---------------------------------------------------------------------------
# A tiny fake merchant agent - implements the exact wire contract
# merchant-agent-core exposes, just enough to script the demo conversation.
# ---------------------------------------------------------------------------
fake_merchant = FastAPI()
_turns: dict[str, int] = {}


@fake_merchant.post("/agent/message")
async def agent_message(request: Request):
    body = await request.json()
    session_id = body["sessionId"]
    message = body["message"].lower()
    turn = _turns.get(session_id, 0)
    _turns[session_id] = turn + 1

    if "checkout" in message or "proceed" in message:
        return {
            "requestId": "req-1",
            "status": "SUCCESS",
            "message": "Order created. Complete payment here: http://localhost:9999/pay/order123",
            "data": {"paymentUrl": "http://localhost:9999/pay/order123"},
        }
    if "verify" in message or "payment is complete" in message or "paid" in message:
        return {"requestId": "req-2", "status": "SUCCESS", "message": "Payment verified. Order #1234 confirmed.", "data": None}
    return {
        "requestId": "req-0",
        "status": "SUCCESS",
        "message": "Yes, iPhone 15 128GB is in stock at ₹64,999.",
        "data": None,
    }


def _run_fake_merchant():
    uvicorn.run(fake_merchant, host="127.0.0.1", port=9999, log_level="warning")


# ---------------------------------------------------------------------------
# A scripted LLMClient standing in for a real model, so the demo is
# deterministic. Each call returns the next line of a canned script.
# ---------------------------------------------------------------------------
class ScriptedLLMClient(LLMClient):
    def __init__(self, script: list[dict]):
        self._script = script
        self._i = 0

    def generate(self, messages) -> LLMResponse:
        decision = self._script[self._i]
        self._i += 1
        return LLMResponse(content=json.dumps(decision))


def main():
    thread = threading.Thread(target=_run_fake_merchant, daemon=True)
    thread.start()
    time.sleep(1.0)

    import os
    os.environ["REGISTRY_ENCRYPTION_KEY"] = "rMqEJMfYN43epWMsOCFQvBcQuam4X0R-ChHcN1Jie0I="
    os.environ["LLM_PROVIDER"] = "local"

    app = build_app()
    client = TestClient(app)

    manifest = {
        "name": "TechHaven India",
        "description": "Electronics, smartphones, and accessories",
        "agentUrl": "http://127.0.0.1:9999/agent/message",
        "authToken": "Bearer dev-token-techhaven",
    }
    r = client.post("/registry", json=manifest)
    merchant_id = r.json()["id"]
    print("Registered merchant:", merchant_id)

    # --- Turn 1: "buy me an iphone" -> search, contact, present offers ---
    from app.gateway import wiring  # noqa
    from app.gateway.wiring import build_app as _b  # ensure importable

    # Monkeypatch the BuyerAgent's LLM with a script for this turn.
    buyer_agent = app.dependency_overrides[__import__("app.gateway.routes", fromlist=["get_buyer_agent"]).get_buyer_agent]()
    buyer_agent._planner._llm_client = ScriptedLLMClient([
        {"action": "SEARCH_MERCHANTS", "search_query": "iphone"},
        {"action": "CONTACT_MERCHANTS", "merchant_ids": [merchant_id],
         "message_to_merchants": "Do you have an iPhone 15 in stock and at what price?"},
        {"action": "PRESENT_OFFERS", "response": "TechHaven has the iPhone 15 128GB for ₹64,999. Want me to buy it there?"},
    ])

    r1 = client.post("/buyer/chat", json={"message": "buy me an iphone"})
    print("\nTurn 1:", r1.json())
    chat_id = r1.json()["chatId"]
    assert r1.json()["status"] == "WAITING_FOR_USER"

    # --- Turn 2: "yes" -> checkout ---
    buyer_agent._planner._llm_client = ScriptedLLMClient([
        {"action": "CHECKOUT", "merchant_ids": [merchant_id],
         "message_to_merchants": "Proceed to checkout: iPhone 15 128GB, qty 1"},
        {"action": "FINAL_RESPONSE", "response": "Here is your payment link: http://localhost:9999/pay/order123. Let me know once you've paid."},
    ])
    r2 = client.post("/buyer/chat", json={"chatId": chat_id, "message": "yes"})
    print("\nTurn 2:", r2.json())
    assert r2.json()["status"] == "COMPLETED"

    # --- Turn 3: "paid" -> confirm payment ---
    buyer_agent._planner._llm_client = ScriptedLLMClient([
        {"action": "CONFIRM_PAYMENT", "merchant_ids": [merchant_id],
         "message_to_merchants": "The user says payment is complete, please verify."},
        {"action": "FINAL_RESPONSE", "response": "Purchase completed! Order #1234 is confirmed with TechHaven."},
    ])
    r3 = client.post("/buyer/chat", json={"chatId": chat_id, "message": "paid"})
    print("\nTurn 3:", r3.json())
    assert r3.json()["status"] == "COMPLETED"
    assert "confirmed" in r3.json()["message"].lower()

    print("\nSMOKE TEST PASSED")


if __name__ == "__main__":
    main()
