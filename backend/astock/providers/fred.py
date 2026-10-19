"""FRED：联邦基金目标利率上限 DFEDTARU。"""


import csv
import io

import httpx

from astock.providers._shared.http import FRED_HTTP_TIMEOUT
from astock.providers._shared.parsing import parse_iso_date, to_float
from astock.providers._shared.retry import retry_call

FRED_DFEDTARU_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFEDTARU"


def fetch_dfedtaru_events() -> list[tuple[str, float]]:
    """返回 [(effective_date YYYY-MM-DD, upper_rate), ...] 升序。"""
    def _download() -> str:
        with httpx.Client(
            timeout=FRED_HTTP_TIMEOUT,
            headers={"User-Agent": "Astock/1.0", "Accept": "text/csv,*/*"},
            http2=False,
        ) as client:
            resp = client.get(FRED_DFEDTARU_URL)
            resp.raise_for_status()
            return resp.text

    text = retry_call("fred_dfedtaru", _download)

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
