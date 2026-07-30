"""美联储目标利率上限：FRED DFEDTARU 主源 + 美联储官网静态 CSV 备源。"""

from __future__ import annotations

import csv
import io
import logging
from typing import Any

import httpx

from astock.sources.fetch_result import SourceFetchResult
from astock.sources.us_macro._common import (
    FRED_HTTP_TIMEOUT,
    http_get_text,
    month_end,
    parse_iso_date,
    to_float,
)

logger = logging.getLogger(__name__)

FRED_DFEDTARU_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFEDTARU"
FED_TARGET_CSV_URL = (
    "https://www.federalreserve.gov/aboutthefed/files/target-funds-2014-2024.csv"
)


def _events_to_monthly(
    events: list[tuple[str, float]],
) -> list[dict[str, Any]]:
    """事件/日频序列 → 月末有效上限。

    events: [(effective_date YYYY-MM-DD, upper_rate), ...] 按日期升序。
    """
    if not events:
        return []
    events = sorted(events, key=lambda x: x[0])
    # 去重：同日保留最后一次
    by_date: dict[str, float] = {}
    for d, v in events:
        by_date[d] = v
    ordered = sorted(by_date.items(), key=lambda x: x[0])

    start_period = ordered[0][0][:7]
    end_period = ordered[-1][0][:7]
    periods: list[str] = []
    y, m = int(start_period[:4]), int(start_period[5:7])
    ey, em = int(end_period[:4]), int(end_period[5:7])
    while (y, m) <= (ey, em):
        periods.append(f"{y:04d}-{m:02d}")
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1

    records: list[dict[str, Any]] = []
    idx = 0
    current_rate: float | None = None
    for period in periods:
        end = month_end(period)
        while idx < len(ordered) and ordered[idx][0] <= end:
            current_rate = ordered[idx][1]
            idx += 1
        if current_rate is None:
            continue
        records.append(
            {
                "period": period,
                "fed_rate_upper": round(current_rate, 4),
            }
        )
    return records


def fetch_fed_rate_fred() -> SourceFetchResult:
    """FRED DFEDTARU 日频目标上限 CSV。"""
    try:
        # 境内跨境常慢，短超时 + 少重试，尽快回退官网 CSV
        last_exc: Exception | None = None
        text = ""
        for attempt in range(2):
            try:
                with httpx.Client(
                    timeout=FRED_HTTP_TIMEOUT,
                    headers={"User-Agent": "Astock/1.0", "Accept": "text/csv,*/*"},
                    http2=False,
                ) as client:
                    resp = client.get(FRED_DFEDTARU_URL)
                    resp.raise_for_status()
                    text = resp.text
                    break
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning("fred_dfedtaru 第 %s 次失败: %s", attempt + 1, exc)
        else:
            return SourceFetchResult.failure(f"FRED DFEDTARU: {last_exc}")
    except Exception as exc:  # noqa: BLE001
        return SourceFetchResult.failure(f"FRED DFEDTARU: {exc}")

    reader = csv.DictReader(io.StringIO(text))
    events: list[tuple[str, float]] = []
    for row in reader:
        # 兼容 observation_date / DATE
        raw_date = row.get("observation_date") or row.get("DATE") or row.get("date")
        d = parse_iso_date(raw_date)
        # 值列名 DFEDTARU
        value = None
        for key, val in row.items():
            if key and key.upper() == "DFEDTARU":
                value = to_float(val)
                break
        if value is None:
            # 第二列兜底
            vals = list(row.values())
            if len(vals) >= 2:
                value = to_float(vals[1])
        if not d or value is None:
            continue
        events.append((d, value))

    records = _events_to_monthly(events)
    if not records:
        return SourceFetchResult.failure("FRED DFEDTARU：无有效数据")
    return SourceFetchResult(records=records, ok=True)


def fetch_fed_rate_official() -> SourceFetchResult:
    """美联储官网转置 CSV：第 1 行日期、第 3 行上限。"""
    try:
        text = http_get_text(FED_TARGET_CSV_URL, label="fed_target_csv")
    except Exception as exc:  # noqa: BLE001
        return SourceFetchResult.failure(f"Fed 官网 CSV: {exc}")

    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 3:
        return SourceFetchResult.failure("Fed 官网 CSV：行数不足")

    dates_row = rows[0]
    upper_row = rows[2]
    events: list[tuple[str, float]] = []
    for raw_date, raw_upper in zip(dates_row, upper_row, strict=False):
        d = parse_iso_date(raw_date)
        value = to_float(raw_upper)
        if not d or value is None:
            continue
        events.append((d, value))

    records = _events_to_monthly(events)
    if not records:
        return SourceFetchResult.failure("Fed 官网 CSV：无有效数据")
    return SourceFetchResult(records=records, ok=True)


def fetch_fed_rate() -> SourceFetchResult:
    """利率：FRED 主源，失败或最新观测异常时回退官网 CSV。"""
    primary = fetch_fed_rate_fred()
    latest_ok = False
    if primary.ok and primary.records:
        latest = primary.records[-1]["period"]
        # 最新月末利率应不早于近 4 个月（利率可能长期不变，用 period 新鲜度）
        from datetime import date

        today = date.today()
        try:
            ly, lm = int(latest[:4]), int(latest[5:7])
            months_behind = (today.year - ly) * 12 + (today.month - lm)
            latest_ok = 0 <= months_behind <= 4
        except (TypeError, ValueError):
            latest_ok = False

    if primary.ok and primary.records and latest_ok:
        return primary

    logger.warning(
        "Fed 利率主源不可用或滞后，回退官网 CSV (ok=%s records=%s latest_ok=%s)",
        primary.ok,
        len(primary.records),
        latest_ok,
    )
    fallback = fetch_fed_rate_official()
    if fallback.ok and fallback.records:
        # 主源失败但备源成功：仅打日志，不把主源超时记为业务错误
        if not primary.ok:
            logger.info(
                "Fed 利率使用官网 CSV 备源（主源错误: %s）",
                primary.error_summary(),
            )
        return fallback
    if primary.records:
        primary.ok = False
        primary.errors.append(fallback.error_summary() or "Fed 官网回退失败")
        return primary
    return SourceFetchResult.failure(
        "; ".join(
            filter(
                None,
                [
                    primary.error_summary(),
                    fallback.error_summary(),
                    "Fed 利率主备源均失败",
                ],
            )
        )
    )
