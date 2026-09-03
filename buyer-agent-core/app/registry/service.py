from __future__ import annotations

import re
import uuid
from typing import Optional

from app.registry.crypto import TokenCipher
from app.registry.models import MerchantEntry, MerchantEntryPublic, MerchantManifest
from app.registry.store import RegistryStore


class RegistryValidationError(Exception):
    pass


class RegistryService:
    """Add/list/delete merchants, and resolve a merchant's *decrypted*
    credentials at the one moment a real call needs them
    (see resolve_for_call). Nothing else touches TokenCipher directly."""

    def __init__(self, store: RegistryStore, cipher: TokenCipher):
        self._store = store
        self._cipher = cipher

    def add(self, manifest: MerchantManifest) -> MerchantEntryPublic:
        _validate_manifest(manifest)
        entry = MerchantEntry(
            id=f"m-{uuid.uuid4().hex[:10]}",
            shopName=manifest.name.strip(),
            description=manifest.description.strip(),
            agentUrl=manifest.agentUrl.strip(),
            authTokenEncrypted=self._cipher.encrypt(manifest.authToken.strip()),
            contactPhone=(manifest.contactPhone or "").strip() or None,
        )
        self._store.add(entry)
        return MerchantEntryPublic.from_entry(entry)

    def list(self) -> list[MerchantEntryPublic]:
        return [MerchantEntryPublic.from_entry(e) for e in self._store.list()]

    def delete(self, merchant_id: str) -> bool:
        return self._store.delete(merchant_id)

    def resolve_for_call(self, merchant_id: str) -> tuple[MerchantEntry, str]:
        """Returns (entry, decrypted_auth_token). This is the only method
        in the whole service that produces a plaintext token, and it's
        called immediately before an outbound HTTP request - never cached,
        never logged, never put on any response object."""
        entry = self._store.get(merchant_id)
        if entry is None:
            raise RegistryValidationError(f"Unknown merchant id: {merchant_id}")
        return entry, self._cipher.decrypt(entry.auth_token_encrypted)

    def get_many_public(self, merchant_ids: list[str]) -> list[MerchantEntryPublic]:
        wanted = set(merchant_ids)
        return [m for m in self.list() if m.id in wanted]

    def all_for_matching(self) -> list[MerchantEntryPublic]:
        """Cheap alias of list(), named for where it's used (RegistryTool),
        so callers reading tools/registry_tool.py don't need to know this
        is the same data as the browser sees."""
        return self.list()


def _validate_manifest(manifest: MerchantManifest) -> None:
    if not manifest.name.strip():
        raise RegistryValidationError("Shop name is required")
    if not manifest.authToken.strip():
        raise RegistryValidationError("Auth token is required")
    if not re.match(r"^https?://", manifest.agentUrl.strip()):
        raise RegistryValidationError("Agent URL must start with http:// or https://")
