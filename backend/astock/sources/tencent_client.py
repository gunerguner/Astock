"""腾讯行情接口：批量获取个股总市值快照，无需鉴权，替代 akshare 实时快照。

实测东方财富（akshare 底层）在本环境下频繁 Connection aborted，
腾讯 qt.gtimg.cn 接口稳定性验证：400 只股票分 7 批全部成功，耗时 0.6 秒。
"""

import logging
import re
from collections.abc import Callable, Iterator

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
    def iter_market_cap_batches(
        self,
        codes: list[str],
    ) -> Iterator[tuple[int, int, list[dict], str | None]]:
        """按批拉取市值；yield (batch_idx, total_batches, records, error)。"""
        if not codes:
            return

        total_batches = (len(codes) + TENCENT_BATCH_SIZE - 1) // TENCENT_BATCH_SIZE
        with httpx.Client(timeout=TENCENT_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"}) as client:
            for batch_idx, i in enumerate(range(0, len(codes), TENCENT_BATCH_SIZE), start=1):
                batch = codes[i : i + TENCENT_BATCH_SIZE]
                query = ",".join(_to_tencent_code(c) for c in batch)
                try:
                    resp = client.get(TENCENT_QUOTE_URL + query)
                    resp.encoding = "gbk"
                    text = resp.text
                except Exception as e:
                    msg = f"腾讯行情批次失败(codes={batch[:3]}...): {e}"
                    logger.warning(msg)
                    yield batch_idx, total_batches, [], msg
                    continue

                records: list[dict] = []
                for _, digits, raw in _LINE_RE.findall(text):
                    market_cap = _parse_market_cap(raw)
                    if market_cap is not None:
                        records.append({"code": digits, "market_cap": market_cap})
                yield batch_idx, total_batches, records, None

    def fetch_market_caps(
        self,
        codes: list[str],
        *,
        on_batch: Callable[[int, int], None] | None = None,
    ) -> SourceFetchResult:
        """codes 为 6 位股票代码列表；返回 records=[{code, market_cap}]（market_cap 单位：元）。"""
        if not codes:
            return SourceFetchResult()

        records: list[dict] = []
        errors: list[str] = []
        for batch_idx, total_batches, batch_records, error in self.iter_market_cap_batches(codes):
            if on_batch is not None:
                on_batch(batch_idx, total_batches)
            if error:
                errors.append(error)
            else:
                records.extend(batch_records)

        ok = len(errors) == 0
        logger.info(
            "腾讯行情市值快照完成: %s/%s 只解析成功, ok=%s", len(records), len(codes), ok
        )
        return SourceFetchResult(records=records, ok=ok, errors=errors)
