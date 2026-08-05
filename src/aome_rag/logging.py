"""Structured logging via structlog, with best-effort secret redaction.

Logs are written to the console (as before) AND, when enabled, to files split
by top-level module under ``<log_dir>/app/`` plus uvicorn's request logs under
``<log_dir>/access/``. Each file rotates daily and keeps ``retention_days``
backups. Every toggle defaults to on; ``log_dir=None`` keeps the old
console-only behaviour.

Naming (TimedRotatingFileHandler with a custom namer): the live file is
``<name>.log``; after midnight it is rotated to ``<name>-YYYY-MM-DD.log``.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path

import structlog

# Substrings that mark a log key as sensitive → value is replaced with "***".
_SENSITIVE_HINTS = ("key", "token", "secret", "authorization", "password", "cookie")

# Top-level packages under aome_rag that get their own file in logs/app/.
# Anything else under aome_rag lands in logs/app/other.log.
APP_MODULES = (
    "api",
    "agent",
    "retrieval",
    "ingestion",
    "cleaning",
    "session",
    "tools",
    "providers",
)

# loggers whose handlers we installed (logger name -> [handlers]) so a second
# configure_logging() call (or a test) can detach them cleanly.
_MANAGED: dict[str, list[logging.Handler]] = {}


def _redact_secrets(_logger, _name, event_dict: dict) -> dict:
    for key in list(event_dict):
        lk = key.lower()
        if any(hint in lk for hint in _SENSITIVE_HINTS):
            event_dict[key] = "***"
    return event_dict


def _detach_managed() -> None:
    for name, handlers in _MANAGED.items():
        logger = logging.getLogger(name)
        for h in handlers:
            if h in logger.handlers:
                logger.removeHandler(h)
    _MANAGED.clear()


def _daily_file_handler(
    path: Path, formatter: logging.Formatter, retention_days: int
) -> logging.Handler:
    os.makedirs(path.parent, exist_ok=True)
    handler = logging.handlers.TimedRotatingFileHandler(
        str(path), when="MIDNIGHT", interval=1, backupCount=retention_days, encoding="utf-8"
    )
    handler.namer = _dated_namer
    handler.setFormatter(formatter)
    return handler


def _dated_namer(default_name: str) -> str:
    """'api.log.2026-08-06' → 'api-2026-08-06.log'."""
    stem, suffix = default_name.rsplit(".", 1)
    base, ext = os.path.splitext(stem)
    return f"{base}-{suffix}{ext}"


class _ExcludeModulesFilter(logging.Filter):
    """Reject records whose logger is one of the module-specific loggers.

    Lets logs/app/other.log catch only aome_rag loggers that don't have their
    own file (so the module files and other.log never both write the same line).
    """

    def __init__(self, modules: tuple[str, ...]) -> None:
        super().__init__()
        self._prefixes = [f"aome_rag.{m}" for m in modules]

    def filter(self, record: logging.LogRecord) -> bool:
        return not any(record.name == p or record.name.startswith(p + ".") for p in self._prefixes)


def _structlog_chain() -> list:
    """Processors applied to structlog events before rendering."""
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        _redact_secrets,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]


_FOREIGN_PRE_CHAIN = [
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt="iso"),
    _redact_secrets,
]


def _readable_formatter() -> structlog.stdlib.ProcessorFormatter:
    """Plain-text rendering shared by console and files (same look as before)."""
    return structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_FOREIGN_PRE_CHAIN,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(colors=False),
        ],
    )


def _setup_root_console(level: int, formatter: logging.Formatter) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)
    _MANAGED.setdefault("", []).append(console)


def _setup_app_files(
    app_dir: Path, level: int, formatter: logging.Formatter, retention_days: int
) -> None:
    for mod in APP_MODULES:
        logger = logging.getLogger(f"aome_rag.{mod}")
        logger.setLevel(level)
        handler = _daily_file_handler(app_dir / f"{mod}.log", formatter, retention_days)
        logger.addHandler(handler)
        _MANAGED.setdefault(logger.name, []).append(handler)

    # Catch-all for any other aome_rag.* logger (e.g. aome_rag.services).
    fallback = logging.getLogger("aome_rag")
    fallback.setLevel(level)
    handler = _daily_file_handler(app_dir / "other.log", formatter, retention_days)
    handler.addFilter(_ExcludeModulesFilter(APP_MODULES))
    fallback.addHandler(handler)
    _MANAGED.setdefault(fallback.name, []).append(handler)


def _setup_uvicorn_loggers(
    app_dir: Path, access_dir: Path, level: int,
    retention_days: int, app_to_file: bool, access_to_file: bool,
) -> None:
    """Route uvicorn's own loggers to console (+ files). Replaces uvicorn's
    default stderr handlers so startup/access lines appear once."""

    from uvicorn.logging import AccessFormatter, DefaultFormatter

    datefmt = "%Y-%m-%d %H:%M:%S"
    console_error = logging.StreamHandler()
    console_error.setFormatter(
        DefaultFormatter(fmt="%(asctime)s %(levelprefix)s %(message)s", datefmt=datefmt)
    )
    console_access = logging.StreamHandler()
    console_access.setFormatter(
        AccessFormatter(
            fmt='%(asctime)s %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s',
            datefmt=datefmt,
        )
    )

    error_file = access_file = None
    if app_to_file:
        error_file = _daily_file_handler(
            app_dir / "uvicorn.log", _readable_formatter(), retention_days
        )
    if access_to_file:
        access_file = _daily_file_handler(
            access_dir / "access.log",
            AccessFormatter(
                fmt=(
                    '%(asctime)s %(levelprefix)s %(client_addr)s '
                    '- "%(request_line)s" %(status_code)s'
                ),
                datefmt=datefmt,
                use_colors=False,
            ),
            retention_days,
        )

    # uvicorn + uvicorn.error → lifecycle/startup/errors
    for name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.setLevel(level)
        logger.propagate = False
        logger.addHandler(console_error)
        if error_file is not None:
            logger.addHandler(error_file)
        _MANAGED[name] = logger.handlers

    # uvicorn.access → per-request lines
    logger = logging.getLogger("uvicorn.access")
    logger.handlers = []
    logger.setLevel(level)
    logger.propagate = False
    logger.addHandler(console_access)
    if access_file is not None:
        logger.addHandler(access_file)
    _MANAGED[logger.name] = logger.handlers


def configure_logging(
    level: str = "INFO",
    *,
    log_dir: str | Path | None = None,
    log_to_file: bool = True,
    log_app_to_file: bool = True,
    log_access_to_file: bool = True,
    retention_days: int = 30,
) -> None:
    """Configure structlog + file logging. Safe to call more than once.

    With ``log_dir=None`` (or ``log_to_file=False``) behaviour is the old
    console-only one.
    """
    _detach_managed()
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    structlog.configure(
        processors=_structlog_chain(),
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = _readable_formatter()
    _setup_root_console(numeric_level, formatter)

    write_files = log_dir is not None and log_to_file
    if not write_files:
        # keep uvicorn's own default stderr output when not writing files
        return

    root = Path(log_dir)
    if log_app_to_file:
        _setup_app_files(root / "app", numeric_level, formatter, retention_days)
    _setup_uvicorn_loggers(
        root / "app", root / "access", numeric_level,
        retention_days, app_to_file=log_app_to_file, access_to_file=log_access_to_file,
    )
