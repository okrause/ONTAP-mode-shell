"""Logging setup shared by GCNV clients."""

from __future__ import annotations

import logging
import os


def configure_logging() -> None:
    """Set root log level from NETAPP_DEBUG."""
    level = logging.DEBUG if os.getenv("NETAPP_DEBUG") else logging.WARNING
    logging.getLogger().setLevel(level)
