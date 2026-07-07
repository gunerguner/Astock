"""Redis 客户端封装：按日期缓存资产收盘价快照。"""

import json
import logging
from typing import Any

import redis

from astock.config import REDIS_URL

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None
_client_failed = False


def _get_client() -> redis.Redis | None:
    global _client, _client_failed
    if _client_failed:
        return None
    if _client is not None:
        return _client
    try:
        _client = redis.from_url(REDIS_URL, decode_responses=True)
        _client.ping()
        return _client
    except Exception as e:
        logger.warning("Redis 不可用，将降级直连数据源: %s", e)
        _client_failed = True
        return None


def get_string(key: str) -> str | None:
    client = _get_client()
    if client is None:
        return None
    try:
        return client.get(key)
    except Exception as e:
        logger.warning("Redis GET 失败 key=%s: %s", key, e)
        return None


def set_string(key: str, value: str, *, ttl: int | None = None) -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        if ttl is not None:
            client.setex(key, ttl, value)
        else:
            client.set(key, value)
        return True
    except Exception as e:
        logger.warning("Redis SET 失败 key=%s: %s", key, e)
        return False


def get_json(key: str) -> Any | None:
    raw = get_string(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Redis JSON 解析失败 key=%s", key)
        return None


def set_json(key: str, value: Any, *, ttl: int | None = None) -> bool:
    return set_string(key, json.dumps(value, ensure_ascii=False), ttl=ttl)


def price_key(ticker: str, date: str) -> str:
    return f"global_asset:price:{ticker}:{date}"


def recent_closes_key(ticker: str) -> str:
    return f"global_asset:recent:{ticker}"


LATEST_TRADING_DATE_KEY = "global_asset:meta:latest_trading_date"
