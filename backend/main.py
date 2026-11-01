import logging
import os

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from app import app  # noqa: E402  (logging must be configured first)

__all__ = ["app"]
