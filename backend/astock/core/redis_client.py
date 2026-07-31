"""Redis 客户端封装：连接网关与通用读写。"""

import json
import logging
import time
from typing import Any

import redis

from astock.config import REDIS_RETRY_COOLDOWN, REDIS_URL

logger = logging.getLogger(__name__)


class RedisGateway:
    def __init__(self) -> None:
        self._client: redis.Redis | None = None
        self._failed_at: float | None = None

    def get(self) -> redis.Redis | None:
        if self._client is not None:
            return self._client
        if self._failed_at is not None:
            if time.monotonic() - self._failed_at < REDIS_RETRY_COOLDOWN:
                return None
            logger.info("Redis 冷却结束，尝试重新连接")
            self._failed_at = None
        try:
            self._client = redis.from_url(REDIS_URL, decode_responses=True)
            self._client.ping()
            return self._client
        except Exception as e:
            logger.warning("Redis 不可用，将降级直连数据源: %s", e)
            self._failed_at = time.monotonic()
            self._client = None
            return None

    def get_string(self, key: str) -> str | None:
        client = self.get()
        if client is None:
            return None
        try:
            return client.get(key)
        except Exception as e:
            logger.warning("Redis GET 失败 key=%s: %s", key, e)
            return None

    def set_string(self, key: str, value: str, *, ttl: int | None = None) -> bool:
        client = self.get()
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

    def delete_key(self, key: str) -> bool:
        client = self.get()
        if client is None:
            return False
        try:
            client.delete(key)
            return True
        except Exception as e:
            logger.warning("Redis DEL 失败 key=%s: %s", key, e)
            return False

    def get_json(self, key: str) -> Any | None:
        raw = self.get_string(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Redis JSON 解析失败 key=%s", key)
            return None

    def set_json(self, key: str, value: Any, *, ttl: int | None = None) -> bool:
        return self.set_string(key, json.dumps(value, ensure_ascii=False), ttl=ttl)


redis_gateway = RedisGateway()
