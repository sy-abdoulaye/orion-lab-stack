"""Configuration de logging partagée."""

from __future__ import annotations

import logging

from common.config import settings

_CONFIGURED = False


def get_logger(name: str) -> logging.Logger:
    global _CONFIGURED
    if not _CONFIGURED:
        logging.basicConfig(
            level=getattr(logging, settings.log_level, logging.INFO),
            format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        )
        _CONFIGURED = True
    return logging.getLogger(name)
