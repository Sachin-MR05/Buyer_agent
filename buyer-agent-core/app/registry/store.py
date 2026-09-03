from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.persistence.db import session_scope
from app.persistence.models import MerchantRow
from app.registry.models import MerchantEntry


class RegistryStore:
    """Persists MerchantEntry rows in Postgres.

    Same public interface as the JSON-file implementation it replaces
    (app/registry/json_store.py) - RegistryService talks only to
    list/get/add/delete, so nothing above this layer needed to change.
    """

    def __init__(self, session_factory: sessionmaker):
        self._session_factory = session_factory

    def list(self) -> list[MerchantEntry]:
        with session_scope(self._session_factory) as session:
            rows = session.scalars(select(MerchantRow).order_by(MerchantRow.created_at.desc())).all()
            return [_to_entry(r) for r in rows]

    def get(self, merchant_id: str) -> Optional[MerchantEntry]:
        with session_scope(self._session_factory) as session:
            row = session.get(MerchantRow, merchant_id)
            return _to_entry(row) if row else None

    def add(self, entry: MerchantEntry) -> MerchantEntry:
        with session_scope(self._session_factory) as session:
            row = MerchantRow(
                id=entry.id,
                shop_name=entry.shop_name,
                description=entry.description,
                agent_url=entry.agent_url,
                auth_token_encrypted=entry.auth_token_encrypted,
                contact_phone=entry.contact_phone,
                created_at=entry.created_at,
            )
            session.add(row)
        return entry

    def delete(self, merchant_id: str) -> bool:
        with session_scope(self._session_factory) as session:
            row = session.get(MerchantRow, merchant_id)
            if row is None:
                return False
            session.delete(row)
            return True


def _to_entry(row: MerchantRow) -> MerchantEntry:
    return MerchantEntry(
        id=row.id,
        shopName=row.shop_name,
        description=row.description,
        agentUrl=row.agent_url,
        authTokenEncrypted=row.auth_token_encrypted,
        contactPhone=row.contact_phone,
        createdAt=row.created_at,
    )
