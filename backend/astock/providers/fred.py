"""FRED：联邦基金目标利率上限 DFEDTARU。"""

from __future__ import annotations

import csv
import io
import logging

import httpx

from astock.providers._shared.http import FRED_HTTP_TIMEOUT
from astock.providers._shared.parsing import parse_iso_date, to_float

logger = logging.getLogger(__name__)

FRED_DFEDTARU_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFEDTARU"


def fetch_dfedtaru_events() -> list[tuple[str, float]]:
    """返回 [(effective_date YYYY-MM-DD, upper_rate), ...] 升序。"""
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
        raise RuntimeError(f"FRED DFEDTARU: {last_exc}")

    reader = csv.DictReader(io.StringIO(text))
    events: list[tuple[str, float]] = []
    for row in reader:
        raw_date = row.get("observation_date") or row.get("DATE") or row.get("date")
        d = parse_iso_date(raw_date)
        value = None
        for key, val in row.items():
            if key and key.upper() == "DFEDTARU":
                value = to_float(val)
                break
        if value is None:
            vals = list(row.values())
            if len(vals) >= 2:
                value = to_float(vals[1])
        if not d or value is None:
            continue
        events.append((d, value))
    return events
