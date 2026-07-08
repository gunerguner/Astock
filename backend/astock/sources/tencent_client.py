"""腾讯行情接口：批量获取个股总市值快照，无需鉴权，替代 akshare 实时快照。

实测东方财富（akshare 底层）在本环境下频繁 Connection aborted，
腾讯 qt.gtimg.cn 接口稳定性验证：400 只股票分 7 批全部成功，耗时 0.6 秒。
"""

import logging
import re

import httpx

from astock.config import (
    TENCENT_BATCH_SIZE,
    TENCENT_MARKET_CAP_FIELD_INDEX,
    TENCENT_QUOTE_URL,
    TENCENT_TIMEOUT,
)
from astock.sources.fetch_result import SourceFetchResult

logger = logging.getLogger(__name__)

_LINE_RE = re.compile(r'v_(sh|sz)(\d{6})="([^"]*)"')


def _to_tencent_code(code: str) -> str:
    prefix = "sh" if code.startswith("6") else "sz"
    return f"{prefix}{code}"


def _parse_market_cap(raw: str) -> float | None:
    fields = raw.split("~")
    if len(fields) <= TENCENT_MARKET_CAP_FIELD_INDEX:
        return None
    try:
        return float(fields[TENCENT_MARKET_CAP_FIELD_INDEX]) * 1e8
    except ValueError:
        return None


class TencentQuoteClient:
    def fetch_market_caps(self, codes: list[str]) -> SourceFetchResult:
        """codes 为 6 位股票代码列表；返回 records=[{code, market_cap}]（market_cap 单位：元）。"""
        if not codes:
            return SourceFetchResult()

        records: list[dict] = []
        errors: list[str] = []

        with httpx.Client(timeout=TENCENT_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"}) as client:
            for i in range(0, len(codes), TENCENT_BATCH_SIZE):
                batch = codes[i : i + TENCENT_BATCH_SIZE]
                query = ",".join(_to_tencent_code(c) for c in batch)
                try:
                    resp = client.get(TENCENT_QUOTE_URL + query)
                    resp.encoding = "gbk"
                    text = resp.text
                except Exception as e:
                    msg = f"腾讯行情批次失败(codes={batch[:3]}...): {e}"
                    logger.warning(msg)
                    errors.append(msg)
                    continue

                for _, digits, raw in _LINE_RE.findall(text):
                    market_cap = _parse_market_cap(raw)
                    if market_cap is not None:
                        records.append({"code": digits, "market_cap": market_cap})

        ok = len(errors) == 0
        logger.info(
            "腾讯行情市值快照完成: %s/%s 只解析成功, ok=%s", len(records), len(codes), ok
        )
        return SourceFetchResult(records=records, ok=ok, errors=errors)
