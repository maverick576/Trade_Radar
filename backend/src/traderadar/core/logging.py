"""Structured logging using structlog with secret masking and standard formatting."""

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

SENSITIVE_KEYS = {
    "password",
    "secret",
    "secret_key",
    "token",
    "api_key",
    "bot_token",
    "postgres_password",
    "authorization",
    "cookie",
}


def mask_sensitive_data(
    logger: logging.Logger,  # noqa: ARG001
    method_name: str,  # noqa: ARG001
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Mask sensitive values in log events to prevent accidental credential leakage."""
    for key, val in list(event_dict.items()):
        key_lower = key.lower()
        if any(s in key_lower for s in SENSITIVE_KEYS):
            if isinstance(val, str) and len(val) > 4:
                event_dict[key] = f"{val[:2]}***{val[-2:]}"
            else:
                event_dict[key] = "***"
    return event_dict


def setup_logging(log_level: str = "INFO", json_format: bool = True) -> None:
    """Configure structlog and standard logging."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        mask_sensitive_data,
    ]

    renderer: structlog.types.Processor
    if json_format:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)

    # Suppress excessive noise from external libraries
    for name in ("urllib3", "asyncio", "aiosqlite"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str = "traderadar") -> structlog.stdlib.BoundLogger:
    """Return a configured structlog logger."""
    logger: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(name)
    return logger
