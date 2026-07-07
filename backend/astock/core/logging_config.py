"""应用日志：控制台输出全量；文件分「普通」与「错误」两级。"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from astock.config import settings

_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
_MAX_BYTES = 10 * 1024 * 1024
_BACKUP_COUNT = 5


class _BelowErrorFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < logging.ERROR


def _parse_root_level() -> int:
    name = settings.log_level.upper().strip()
    level = getattr(logging, name, None)
    return level if isinstance(level, int) else logging.INFO


def setup_logging() -> None:
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(_parse_root_level())

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATEFMT)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(root.level)
    console.setFormatter(formatter)
    root.addHandler(console)

    app_path = log_dir / "app.log"
    app_handler = RotatingFileHandler(
        app_path,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    app_handler.setLevel(logging.INFO)
    app_handler.addFilter(_BelowErrorFilter())
    app_handler.setFormatter(formatter)
    root.addHandler(app_handler)

    err_path = log_dir / "error.log"
    err_handler = RotatingFileHandler(
        err_path,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    err_handler.setLevel(logging.ERROR)
    err_handler.setFormatter(formatter)
    root.addHandler(err_handler)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
