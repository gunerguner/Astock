"""腾讯行情接口：批量获取个股市值/成交额快照，无需鉴权。

字段约定（qt.gtimg.cn，`~` 分隔）：
- 1：名称
- 37：成交额（万元）
- 44：总市值（亿元）
"""

import logging
import re
from collections.abc import Callable, Iterator

import httpx

from astock.config import (
    TENCENT_AMOUNT_FIELD_INDEX,
    TENCENT_BATCH_SIZE,
    TENCENT_MARKET_CAP_FIELD_INDEX,
    TENCENT_NAME_FIELD_INDEX,
    TENCENT_QUOTE_URL,
    TENCENT_TIMEOUT,
)
from astock.sources.fetch_result import SourceFetchResult

logger = logging.getLogger(__name__)

_LINE_RE = re.compile(r'v_(sh|sz)(\d{6})="([^"]*)"')


def _to_tencent_code(code: str) -> str:
    prefix = "sh" if code.startswith("6") else "sz"
    return f"{prefix}{code}"


def _parse_float_field(fields: list[str], index: int) -> float | None:
    if len(fields) <= index:
        return None
    raw = fields[index].strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_spot_fields(raw: str) -> tuple[str | None, float | None, float | None]:
    """返回 (name, amount_yuan, market_cap_yuan)。"""
    fields = raw.split("~")
    name = fields[TENCENT_NAME_FIELD_INDEX].strip() if len(fields) > TENCENT_NAME_FIELD_INDEX else None
    amount_wan = _parse_float_field(fields, TENCENT_AMOUNT_FIELD_INDEX)
    cap_yi = _parse_float_field(fields, TENCENT_MARKET_CAP_FIELD_INDEX)
    amount = amount_wan * 1e4 if amount_wan is not None else None
    market_cap = cap_yi * 1e8 if cap_yi is not None else None
    return (name or None), amount, market_cap


def _parse_market_cap(raw: str) -> float | None:
    _, _, market_cap = _parse_spot_fields(raw)
    return market_cap


class TencentQuoteClient:
    def iter_spot_batches(
        self,
        codes: list[str],
    ) -> Iterator[tuple[int, int, list[dict], str | None]]:
        """按批拉取市值+成交额；yield (batch_idx, total_batches, records, error)。

        records 项：{code, name, amount, market_cap}（amount/market_cap 单位：元）。
        """
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
                    name, amount, market_cap = _parse_spot_fields(raw)
                    if market_cap is None and amount is None:
                        continue
                    records.append(
                        {
                            "code": digits,
                            "name": name or "",
                            "amount": amount if amount is not None else 0.0,
                            "market_cap": market_cap if market_cap is not None else 0.0,
                        }
                    )
                yield batch_idx, total_batches, records, None

    def iter_market_cap_batches(
        self,
        codes: list[str],
    ) -> Iterator[tuple[int, int, list[dict], str | None]]:
        """按批拉取市值；yield (batch_idx, total_batches, records, error)。"""
        for batch_idx, total_batches, batch_records, error in self.iter_spot_batches(codes):
            if error:
                yield batch_idx, total_batches, [], error
                continue
            records = [
                {"code": r["code"], "market_cap": r["market_cap"]}
                for r in batch_records
                if r.get("market_cap")
            ]
            yield batch_idx, total_batches, records, None

    def fetch_spot_snapshot(self, codes: list[str]) -> SourceFetchResult:
        """codes 为 6 位股票代码；返回 {code, name, amount, market_cap}（元）。"""
        if not codes:
            return SourceFetchResult()

        records: list[dict] = []
        errors: list[str] = []
        for _, _, batch_records, error in self.iter_spot_batches(codes):
            if error:
                errors.append(error)
            else:
                records.extend(batch_records)

        ok = len(errors) == 0
        logger.info(
            "腾讯行情快照完成: %s/%s 只解析成功, ok=%s", len(records), len(codes), ok
        )
        return SourceFetchResult(records=records, ok=ok, errors=errors)

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
