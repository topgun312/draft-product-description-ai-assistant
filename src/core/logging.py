from __future__ import annotations

import logging
import sys
from pathlib import Path

from loguru import logger

_LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)


class InterceptHandler(logging.Handler):
    """Передавать сообщения стандартного logging в loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        """Перенаправить запись стандартного логгера в loguru."""
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame = logging.currentframe()
        depth = 0
        while frame is not None:
            filename = frame.f_code.co_filename
            if filename not in (__file__, logging.__file__):
                break
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def _intercept_stdlib_logging() -> None:
    """Заменить обработчики стандартных логгеров на InterceptHandler."""
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        stdlib_logger = logging.getLogger(name)
        stdlib_logger.handlers = [InterceptHandler()]
        stdlib_logger.propagate = False


def setup_logging(level: str = "INFO", log_file: str | None = None) -> None:
    """Настроить loguru: вывод в stderr и (опционально) в файл с ротацией."""
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format=_LOG_FORMAT,
        colorize=True,
        backtrace=False,
        diagnose=False,
    )
    _intercept_stdlib_logging()

    if log_file:
        path = Path(log_file)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            logger.add(
                str(path),
                level=level,
                format=_LOG_FORMAT,
                rotation="10 MB",
                retention="7 days",
                compression="zip",
                encoding="utf-8",
                enqueue=True,
                backtrace=False,
                diagnose=False,
            )
        except OSError as e:
            logger.warning("Не удалось открыть файл логов '{}': {}", path, e)

    logger.debug("Логирование настроено: уровень={}, файл={}", level, log_file)
