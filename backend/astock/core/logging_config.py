"""应用日志：控制台输出全量；文件按日分片，分「普通」与「错误」两级。"""


import logging
import sys
from datetime import date, datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from astock.config import settings

_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
# 按自然日滚动；保留最近 N 天分片（当前写入文件 + 历史后缀文件）
_WHEN = "midnight"
_INTERVAL = 1
_APP_BACKUP_DAYS = 30
_ERROR_BACKUP_DAYS = 90
_SUFFIX = "%Y-%m-%d"


class _BelowErrorFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < logging.ERROR


def _parse_root_level() -> int:
    name = settings.log_level.upper().strip()
    level = getattr(logging, name, None)
    return level if isinstance(level, int) else logging.INFO


def _parse_line_date(line: str) -> str | None:
    if len(line) < 10 or line[4] != "-" or line[7] != "-":
        return None
    candidate = line[:10]
    try:
        datetime.strptime(candidate, "%Y-%m-%d")
    except ValueError:
        return None
    return candidate


def _shard_existing_log(path: Path, *, today: str) -> None:
    """把已堆在一起的历史日志按行首日期拆成 path.YYYY-MM-DD，当天留在 path。"""
    if not path.is_file() or path.stat().st_size == 0:
        return

    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        return

    buckets: dict[str, list[str]] = {}
    current_date = today
    for line in text.splitlines(keepends=True):
        parsed = _parse_line_date(line)
        if parsed is not None:
            current_date = parsed
        buckets.setdefault(current_date, []).append(line)

    if set(buckets.keys()) <= {today}:
        return

    for day, lines in buckets.items():
        if day == today:
            continue
        archive = path.with_name(f"{path.name}.{day}")
        with archive.open("a", encoding="utf-8") as fh:
            fh.writelines(lines)

    path.write_text("".join(buckets.get(today, [])), encoding="utf-8")


def _timed_handler(
    path: Path,
    *,
    level: int,
    backup_count: int,
) -> TimedRotatingFileHandler:
    handler = TimedRotatingFileHandler(
        path,
        when=_WHEN,
        interval=_INTERVAL,
        backupCount=backup_count,
        encoding="utf-8",
        utc=False,
    )
    handler.suffix = _SUFFIX
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATEFMT),
    )
    return handler


def setup_logging() -> None:
    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    today = date.today().strftime(_SUFFIX)
    _shard_existing_log(log_dir / "app.log", today=today)
    _shard_existing_log(log_dir / "error.log", today=today)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(_parse_root_level())

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATEFMT)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(root.level)
    console.setFormatter(formatter)
    root.addHandler(console)

    app_handler = _timed_handler(
        log_dir / "app.log",
        level=logging.INFO,
        backup_count=_APP_BACKUP_DAYS,
    )
    app_handler.addFilter(_BelowErrorFilter())
    root.addHandler(app_handler)

    err_handler = _timed_handler(
        log_dir / "error.log",
        level=logging.ERROR,
        backup_count=_ERROR_BACKUP_DAYS,
    )
    root.addHandler(err_handler)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
