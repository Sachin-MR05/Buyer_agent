from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.buyer_agent import BuyerAgent
from app.config.settings import Settings, get_settings
from app.gateway import routes
from app.llm.llm_client import create_llm_client
from app.persistence.chat_store import ChatStore
from app.persistence.db import make_engine, make_session_factory
from app.persistence.models import Base
from app.registry.crypto import TokenCipher
from app.registry.service import RegistryService
from app.registry.store import RegistryStore
from app.tools.merchant_client import MerchantClient
from app.tools.registry_tool import RegistryTool


def build_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(title="Buyer Agent", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.dashboard_cors_origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)  # dev-friendly auto-create; see README for Alembic migration notes
    session_factory = make_session_factory(engine)

    store = RegistryStore(session_factory)
    cipher = TokenCipher(settings)
    registry_service = RegistryService(store, cipher)
    chat_store = ChatStore(session_factory)

    llm_client = create_llm_client(settings)
    registry_tool = RegistryTool(registry_service)
    merchant_client = MerchantClient(settings, registry_service)

    buyer_agent = BuyerAgent(
        llm_client=llm_client,
        registry_tool=registry_tool,
        registry_service=registry_service,
        merchant_client=merchant_client,
        chat_store=chat_store,
        max_iterations=settings.agent_max_iterations,
        max_merchants_per_query=settings.max_merchants_per_query,
    )

    app.dependency_overrides[routes.get_buyer_agent] = lambda: buyer_agent
    app.dependency_overrides[routes.get_registry_service] = lambda: registry_service
    app.include_router(routes.router)

    @app.on_event("shutdown")
    def _shutdown() -> None:
        merchant_client.close()
        engine.dispose()

    return app
