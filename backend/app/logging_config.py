"""Structured-ish logging setup (plan section 31).

Logs timestamp, level, logger name, and message. Challenge routes include
player/challenge/endpoint/result fields in their messages. Secrets (flags) are
never logged.
"""

from __future__ import annotations

import logging


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
