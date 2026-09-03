from __future__ import annotations

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional

import httpx

from app.config.settings import Settings
from app.registry.models import MerchantEntryPublic
from app.registry.service import RegistryService

logger = logging.getLogger(__name__)


class MerchantClientError(Exception):
    """Base error talking to a merchant agent."""


class MerchantUnavailableError(MerchantClientError):
    """The merchant agent could not be reached or returned a server error."""


class MerchantTimeoutError(MerchantClientError):
    """The merchant agent did not respond within merchant_timeout_seconds."""


class MerchantAuthError(MerchantClientError):
    """The merchant rejected our auth token (401)."""


class MalformedMerchantResponseError(MerchantClientError):
    """The merchant responded, but not in the expected AgentResponse shape."""


@dataclass
class MerchantReply:
    """Normalized result of one call to a merchant agent - this is what the
    rest of the Buyer Agent (Executor, Planner) actually reasons about, so
    it never needs to know about HTTP status codes or wire field names."""

    merchant_id: str
    shop_name: str
    request_id: str
    status: str  # SUCCESS | WAITING_FOR_INPUT | WAITING_FOR_CONFIRMATION | REJECTED | FAILED
    message: str
    data: Optional[dict] = None
    error: Optional[str] = None


class MerchantClient:
    """The ONLY place in the service that makes an HTTP call to a merchant
    agent. Speaks exactly the contract merchant-agent-core's
    app/gateway/routes.py exposes:

        POST {agentUrl}
        Authorization: {authToken}
        { "sessionId": str, "userId": str, "message": str, "channel": "api" }
        -> { "requestId", "status", "message", "data", "error" }

    A short client-level timeout is used deliberately - see
    Settings.merchant_timeout_seconds - so one slow or dead shop can never
    stall the others when the Buyer Agent fans a query out to several
    merchants at once.
    """

    def __init__(self, settings: Settings, registry_service: RegistryService, client: Optional[httpx.Client] = None):
        self._settings = settings
        self._registry = registry_service
        self._client = client or httpx.Client(timeout=settings.merchant_timeout_seconds)

    def close(self) -> None:
        self._client.close()

    def send(self, merchant: MerchantEntryPublic, buyer_user_id: str, session_id: str, message: str) -> MerchantReply:
        """Send one message to one merchant agent and return its reply."""
        _, auth_token = self._registry.resolve_for_call(merchant.id)
        request_id = f"buyer-{uuid.uuid4().hex[:10]}"

        body = {
            "requestId": request_id,
            "sessionId": session_id,
            "userId": buyer_user_id,
            "message": message,
            # Must be one of the merchant gateway's ALLOWED_CHANNELS
            # (web/mobile/api/voice/chat) - "api" is the correct value for
            # an agent-to-agent caller like this one. Anything else gets a
            # 400 INVALID_CHANNEL from a spec-compliant merchant gateway.
            "channel": "api",
        }

        logger.info("Contacting merchant '%s' (requestId=%s)", merchant.shop_name, request_id)
        try:
            response = self._client.post(
                merchant.agent_url,
                headers={"Authorization": auth_token},
                json=body,
            )
        except httpx.TimeoutException as exc:
            raise MerchantTimeoutError(f"'{merchant.shop_name}' did not respond in time") from exc
        except httpx.RequestError as exc:
            raise MerchantUnavailableError(f"Could not reach '{merchant.shop_name}': {exc}") from exc

        if response.status_code == 401:
            raise MerchantAuthError(f"'{merchant.shop_name}' rejected our auth token")
        if response.status_code >= 500:
            raise MerchantUnavailableError(f"'{merchant.shop_name}' returned {response.status_code}")
        if response.status_code >= 400:
            raise MerchantClientError(f"'{merchant.shop_name}' rejected the request ({response.status_code})")

        try:
            payload = response.json()
            reply = MerchantReply(
                merchant_id=merchant.id,
                shop_name=merchant.shop_name,
                request_id=payload.get("requestId", request_id),
                status=payload["status"],
                message=payload.get("message", ""),
                data=payload.get("data"),
                error=(payload.get("error") or {}).get("message") if payload.get("error") else None,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise MalformedMerchantResponseError(
                f"'{merchant.shop_name}' returned an unexpected response shape"
            ) from exc

        logger.info("Merchant '%s' replied status=%s", merchant.shop_name, reply.status)
        return reply

    def send_to_many(
        self, merchants: list[MerchantEntryPublic], buyer_user_id: str, session_ids: dict[str, str], message: str
    ) -> list[MerchantReply]:
        """Fan the same message out to several merchants concurrently and
        wait for all of them (each bounded by its own per-call timeout) -
        this is what keeps "find me an iPhone across N shops" fast instead
        of serial. A merchant that errors out is turned into a FAILED
        MerchantReply rather than raising, so one bad shop never sinks the
        whole comparison.
        """
        max_workers = min(len(merchants), self._settings.max_parallel_merchants) or 1
        results: list[MerchantReply] = []
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_to_merchant = {
                pool.submit(self.send, m, buyer_user_id, session_ids[m.id], message): m for m in merchants
            }
            for future in as_completed(future_to_merchant):
                merchant = future_to_merchant[future]
                try:
                    results.append(future.result())
                except MerchantClientError as exc:
                    logger.warning("Merchant '%s' failed: %s", merchant.shop_name, exc)
                    results.append(
                        MerchantReply(
                            merchant_id=merchant.id,
                            shop_name=merchant.shop_name,
                            request_id="",
                            status="FAILED",
                            message="",
                            error=str(exc),
                        )
                    )
        return results
