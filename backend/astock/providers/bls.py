"""BLS Public API：美国 CPI 未季调指数。"""


import logging
from typing import Any

from astock.providers._shared.http import http_get_json
from astock.providers._shared.parsing import to_float

logger = logging.getLogger(__name__)

BLS_SERIES_ID = "CUUR0000SA0"
BLS_API_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/"


def fetch_cpi_index_points(
    *,
    start_year: int,
    end_year: int,
) -> tuple[dict[str, float], list[str]]:
    """按年窗口拉取 CUUR0000SA0 指数；返回 (period→index, errors)。"""
    points: dict[str, float] = {}
    errors: list[str] = []
    year = start_year
    while year <= end_year:
        window_end = min(year + 9, end_year)
        url = (
            f"{BLS_API_URL}{BLS_SERIES_ID}"
            f"?startyear={year}&endyear={window_end}"
        )
        try:
            payload: Any = http_get_json(url, label=f"bls_cpi_{year}_{window_end}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"BLS {year}-{window_end}: {exc}")
            year = window_end + 1
            continue

        status = str(payload.get("status", ""))
        if status != "REQUEST_SUCCEEDED":
            msg = payload.get("message") or status or "unknown"
            errors.append(f"BLS {year}-{window_end}: {msg}")
            year = window_end + 1
            continue

        series_list = (payload.get("Results") or {}).get("series") or []
        if not series_list:
            errors.append(f"BLS {year}-{window_end}: 无 series")
            year = window_end + 1
            continue

        for item in series_list[0].get("data") or []:
            period_code = str(item.get("period") or "")
            if not period_code.startswith("M") or period_code == "M13":
                continue
            try:
                month = int(period_code[1:])
                yr = int(item.get("year"))
            except (TypeError, ValueError):
                continue
            value = to_float(item.get("value"))
            if value is None:
                continue
            points[f"{yr:04d}-{month:02d}"] = value
        year = window_end + 1

    return points, errors
