"""美联储官网：目标利率静态 CSV。"""

from __future__ import annotations

import csv
import io

from astock.providers._shared.http import http_get_text
from astock.providers._shared.parsing import parse_iso_date, to_float

FED_TARGET_CSV_URL = (
    "https://www.federalreserve.gov/aboutthefed/files/target-funds-2014-2024.csv"
)


def fetch_target_rate_events() -> list[tuple[str, float]]:
    """官网转置 CSV：第 1 行日期、第 3 行上限 → [(date, rate), ...]。"""
    text = http_get_text(FED_TARGET_CSV_URL, label="fed_target_csv")
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 3:
        raise RuntimeError("Fed 官网 CSV：行数不足")

    dates_row = rows[0]
    upper_row = rows[2]
    events: list[tuple[str, float]] = []
    for raw_date, raw_upper in zip(dates_row, upper_row, strict=False):
        d = parse_iso_date(raw_date)
        value = to_float(raw_upper)
        if not d or value is None:
            continue
        events.append((d, value))
    return events
