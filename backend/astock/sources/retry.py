"""外部数据源统一重试。"""

import logging
import time
from collections.abc import Callable

from astock.config import FETCH_RETRIES, FETCH_RETRY_DELAY

logger = logging.getLogger(__name__)


def retry_call[T](label: str, fn: Callable[[], T]) -> T:
    last: Exception | None = None
    for attempt in range(FETCH_RETRIES):
        try:
            return fn()
        except Exception as e:
            last = e
            if attempt < FETCH_RETRIES - 1:
                logger.warning("%s 第 %s 次失败，重试: %s", label, attempt + 1, e)
                time.sleep(FETCH_RETRY_DELAY * (attempt + 1))
    assert last is not None
    raise last
