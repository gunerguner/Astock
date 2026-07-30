"""美国 CPI：东方财富主源 + BLS 备源。"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from astock.datasets.macro.common import macro_record
from astock.datasets.result import FetchResult
from astock.models.macro import METRIC_CPI_YOY, REGION_US
from astock.providers._shared.parsing import parse_iso_date, parse_period, to_float
from astock.providers.akshare import economics as ak_econ
from astock.providers import bls

logger = logging.getLogger(__name__)

_SHANGHAI = ZoneInfo("Asia/Shanghai")

# BLS 因 2025 政府停摆未发布 Oct CPI；财政部按 TIPS 应急条款公布 NSA 指数 325.604，
# 相对 BLS 2024-10 指数 315.664 计算同比，补齐图表断点。
_CPI_GAP_YOY: dict[str, float] = {
    "2025-10": round((325.604 / 315.664 - 1.0) * 100.0, 1),
}


def _today_shanghai() -> date:
    return datetime.now(_SHANGHAI).date()


def _fill_known_cpi_gaps(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_period = {str(r["period"]): r for r in records if r.get("period")}
    for period, yoy in _CPI_GAP_YOY.items():
        existing = by_period.get(period)
        if existing is None or existing.get("value") is None:
            by_period[period] = macro_record(
                region=REGION_US, period=period, metric=METRIC_CPI_YOY, value=yoy
            )
    return [by_period[k] for k in sorted(by_period)]


def _normalize_cpi_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    today = _today_shanghai().isoformat()
    out: list[dict[str, Any]] = []
    for row in rows:
        period = row.get("period")
        value = row.get("cpi_yoy")
        if not period or value is None:
            continue
        release = row.get("cpi_release_date")
        if release and release > today:
            continue
        out.append(
            macro_record(
                region=REGION_US,
                period=str(period),
                metric=METRIC_CPI_YOY,
                value=float(value),
            )
        )
    out.sort(key=lambda r: r["period"])
    return _fill_known_cpi_gaps(out)


def fetch_cpi_eastmoney() -> FetchResult:
    df = ak_econ.fetch_usa_cpi_yoy()
    if df is None or df.empty:
        return FetchResult.failure("东方财富 CPI：空结果")

    rows: list[dict[str, Any]] = []
    for _, raw in df.iterrows():
        period = parse_period(raw.get("时间") or raw.get("日期"))
        value = to_float(raw.get("现值"))
        release = parse_iso_date(raw.get("发布日期"))
        if not period:
            continue
        rows.append({"period": period, "cpi_yoy": value, "cpi_release_date": release})
    records = _normalize_cpi_rows(rows)
    if not records:
        return FetchResult.failure("东方财富 CPI：无有效已发布数据")
    return FetchResult(records=records, ok=True)


def _bls_yoy_from_index(points: dict[str, float]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for period, value in sorted(points.items()):
        year, month = int(period[:4]), int(period[5:7])
        prev_key = f"{year - 1:04d}-{month:02d}"
        prev = points.get(prev_key)
        if prev is None or prev == 0:
            continue
        yoy = (value / prev - 1.0) * 100.0
        rows.append({"period": period, "cpi_yoy": yoy})
    return rows


def fetch_cpi_bls(*, start_year: int = 2008) -> FetchResult:
    end_year = _today_shanghai().year
    points, errors = bls.fetch_cpi_index_points(start_year=start_year, end_year=end_year)
    rows = _bls_yoy_from_index(points)
    records = _normalize_cpi_rows(rows)
    if not records:
        msg = "; ".join(errors[:3]) if errors else "BLS CPI：无有效数据"
        return FetchResult.failure(msg)
    fr = FetchResult(records=records, ok=True)
    if errors:
        fr.errors.extend(errors)
    return fr


def fetch_cpi() -> FetchResult:
    """CPI：东财主源，失败/空/明显滞后时回退 BLS。"""
    primary = fetch_cpi_eastmoney()
    expected_lag_ok = False
    if primary.ok and primary.records:
        latest = primary.records[-1]["period"]
        today = _today_shanghai()
        try:
            ly, lm = int(latest[:4]), int(latest[5:7])
            months_behind = (today.year - ly) * 12 + (today.month - lm)
            expected_lag_ok = 0 <= months_behind <= 3
        except (TypeError, ValueError):
            expected_lag_ok = False

    if primary.ok and primary.records and expected_lag_ok:
        return primary

    logger.warning(
        "CPI 主源不可用或滞后，回退 BLS (ok=%s records=%s lag_ok=%s errors=%s)",
        primary.ok,
        len(primary.records),
        expected_lag_ok,
        primary.errors,
    )
    fallback = fetch_cpi_bls()
    if fallback.ok and fallback.records:
        if not primary.ok:
            logger.info("CPI 使用 BLS 备源（主源错误: %s）", primary.error_summary())
        return fallback
    if primary.records:
        primary.ok = False
        primary.errors.append(fallback.error_summary() or "BLS 回退失败")
        return primary
    return FetchResult.failure(
        "; ".join(
            filter(
                None,
                [
                    primary.error_summary(),
                    fallback.error_summary(),
                    "CPI 主备源均失败",
                ],
            )
        )
    )
