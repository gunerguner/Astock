"""美联储目标利率上限：FRED 主源 + 官网 CSV 备源。"""


from typing import Any

from astock.datasets.macro.common import macro_record, with_fallback
from astock.datasets.result import FetchResult
from astock.providers._shared.parsing import month_end
from astock.providers import federal_reserve, fred


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
    return with_fallback(
        fetch_fed_rate_fred(),
        fetch_fed_rate_official,
        max_lag_months=4,
        label="Fed 利率",
        fallback_error_label="Fed 官网回退失败",
    )
