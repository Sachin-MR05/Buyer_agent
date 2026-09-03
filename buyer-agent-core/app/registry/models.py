from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MerchantManifest(BaseModel):
    """The exact shape a shop's AgentInfo page hands out (see
    ecommerce-frontend's merchant_manifest.json / AgentInfo.jsx). The
    registry "add merchant" endpoint accepts this verbatim - it's the
    single copy/paste blob the user drops in."""

    model_config = ConfigDict(extra="ignore")

    name: str
    description: str = ""
    agentUrl: str
    authToken: str
    contactPhone: Optional[str] = None


class MerchantEntry(BaseModel):
    """A stored registry row. authToken never appears here - it lives only
    as authTokenEncrypted, and only registry/crypto.py ever decrypts it,
    at the moment a request is about to be sent to that merchant."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    shop_name: str = Field(alias="shopName")
    description: str
    agent_url: str = Field(alias="agentUrl")
    auth_token_encrypted: str = Field(alias="authTokenEncrypted")
    contact_phone: Optional[str] = Field(default=None, alias="contactPhone")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="createdAt")


class MerchantEntryPublic(BaseModel):
    """What the registry API returns to the browser - never the encrypted
    token, never the plaintext token."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    shop_name: str = Field(alias="shopName")
    description: str
    agent_url: str = Field(alias="agentUrl")
    contact_phone: Optional[str] = Field(default=None, alias="contactPhone")
    created_at: datetime = Field(alias="createdAt")

    @staticmethod
    def from_entry(entry: MerchantEntry) -> "MerchantEntryPublic":
        return MerchantEntryPublic(
            id=entry.id,
            shopName=entry.shop_name,
            description=entry.description,
            agentUrl=entry.agent_url,
            contactPhone=entry.contact_phone,
            createdAt=entry.created_at,
        )
