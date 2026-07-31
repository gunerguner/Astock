"""美联储目标利率上限：FRED 主源 + 官网 CSV 备源。"""


import logging
from datetime import date
from typing import Any

from astock.datasets.macro.common import macro_record
from astock.datasets.result import FetchResult
from astock.providers._shared.parsing import month_end
from astock.providers import federal_reserve, fred

logger = logging.getLogger(__name__)


def _events_to_monthly(events: list[tuple[str, float]]) -> list[dict[str, Any]]:
    if not events:
        return []
    events = sorted(events, key=lambda x: x[0])
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
            macro_record(
                region="us",
                period=period,
                metric="fed_rate_upper",
                value=current_rate,
            )
        )
    return records


def fetch_fed_rate_fred() -> FetchResult:
    try:
        events = fred.fetch_dfedtaru_events()
    except Exception as exc:  # noqa: BLE001
        return FetchResult.failure(f"FRED DFEDTARU: {exc}")
    records = _events_to_monthly(events)
    if not records:
        return FetchResult.failure("FRED DFEDTARU：无有效数据")
    return FetchResult(records=records, ok=True)


def fetch_fed_rate_official() -> FetchResult:
    try:
        events = federal_reserve.fetch_target_rate_events()
    except Exception as exc:  # noqa: BLE001
        return FetchResult.failure(f"Fed 官网 CSV: {exc}")
    records = _events_to_monthly(events)
    if not records:
        return FetchResult.failure("Fed 官网 CSV：无有效数据")
    return FetchResult(records=records, ok=True)


def fetch_fed_rate() -> FetchResult:
    """利率：FRED 主源，失败或最新观测异常时回退官网 CSV。"""
    primary = fetch_fed_rate_fred()
    latest_ok = False
    if primary.ok and primary.records:
        latest = primary.records[-1]["period"]
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
    return FetchResult.failure(
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
