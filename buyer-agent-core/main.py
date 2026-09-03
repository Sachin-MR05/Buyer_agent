import logging

from app.config.settings import get_settings
from app.gateway.wiring import build_app

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = build_app(settings)
