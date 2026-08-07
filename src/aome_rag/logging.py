"""基于 structlog 的结构化日志，含尽力而为的敏感字段脱敏。

日志同时写控制台（保持原行为）与文件；开启时按顶层模块分包到 ``<log_dir>/app/``，
uvicorn 的每个请求日志写到 ``<log_dir>/access/``。每个文件按天轮转并保留
``retention_days`` 份。各开关默认全开；``log_dir=None`` 时保持旧的控制台-only 行为。

命名（TimedRotatingFileHandler + 自定义 namer）：实时文件是 ``<name>.log``，
过午夜轮转成 ``<name>-YYYY-MM-DD.log``。
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path

import structlog

# 含这些子串的日志键视为敏感 → 值替换为 "***"
_SENSITIVE_HINTS = ("key", "token", "secret", "authorization", "password", "cookie")

# aome_rag 下各自独占 logs/app/ 一个文件的顶层包
# aome_rag 下其它日志落入 logs/app/other.log
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

# 我们安装了 handler 的日志器（logger 名 -> [handlers]），以便再次调用
# configure_logging()（或测试）能干净地摘除。
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
    """轮转文件命名：'api.log.2026-08-06' → 'api-2026-08-06.log'（日期进文件名）。"""
    stem, suffix = default_name.rsplit(".", 1)
    base, ext = os.path.splitext(stem)
    return f"{base}-{suffix}{ext}"


class _ExcludeModulesFilter(logging.Filter):
    """过滤掉已有独立文件的模块日志器。

    作用：让 logs/app/other.log 只收纳没有独立文件的 aome_rag.* 日志器
    （如 aome_rag.services），保证模块文件与 other.log 不会同一行重复写两份。
    """

    def __init__(self, modules: tuple[str, ...]) -> None:
        super().__init__()
        self._prefixes = [f"aome_rag.{m}" for m in modules]

    def filter(self, record: logging.LogRecord) -> bool:
        return not any(record.name == p or record.name.startswith(p + ".") for p in self._prefixes)


def _structlog_chain() -> list:
    """structlog 事件在渲染前经过的处理器链（合并上下文 → 级别 → 时间戳 → 脱敏 → 异常信息）。"""
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
    """控制台与文件共用的纯文本渲染（保持与之前一致的可读格式）。"""
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

    # 兜底：其它未分包的 aome_rag.* 日志器（如 aome_rag.services）
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
    """把 uvicorn 自身的日志器改接到控制台（+ 文件）。

    替换 uvicorn 默认的 stderr handler，让启动/访问日志只出现一次；
    uvicorn.error 承载生命周期/错误，uvicorn.access 承载每个请求。"""

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

    # uvicorn + uvicorn.error → 生命周期/启动/错误
    for name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.setLevel(level)
        logger.propagate = False
        logger.addHandler(console_error)
        if error_file is not None:
            logger.addHandler(error_file)
        _MANAGED[name] = logger.handlers

    # uvicorn.access → 每个请求一行
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
    """配置 structlog + 文件日志。可重复调用。

    ``log_dir=None``（或 ``log_to_file=False``）时为旧的控制台-only 行为。
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
        # 不写文件时保留 uvicorn 自身的默认 stderr 输出
        return

    root = Path(log_dir)
    if log_app_to_file:
        _setup_app_files(root / "app", numeric_level, formatter, retention_days)
    _setup_uvicorn_loggers(
        root / "app", root / "access", numeric_level,
        retention_days, app_to_file=log_app_to_file, access_to_file=log_access_to_file,
    )
