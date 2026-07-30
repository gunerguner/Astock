"""美国 CPI 同比抓取：东方财富（akshare）主源 + BLS 备源。"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import akshare as ak
import pandas as pd

from astock.sources.fetch_result import SourceFetchResult
from astock.sources.market_overview._common import safe_retry_df
from astock.sources.us_macro._common import (
    http_get_json,
    parse_iso_date,
    parse_period,
    to_float,
)

logger = logging.getLogger(__name__)

_SHANGHAI = ZoneInfo("Asia/Shanghai")
BLS_SERIES_ID = "CUUR0000SA0"
BLS_API_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/"

# BLS 因 2025 政府停摆未发布 Oct CPI；财政部按 TIPS 应急条款公布 NSA 指数 325.604，
# 相对 BLS 2024-10 指数 315.664 计算同比，补齐图表断点。
_CPI_GAP_YOY: dict[str, float] = {
    "2025-10": round((325.604 / 315.664 - 1.0) * 100.0, 1),
}


def _today_shanghai() -> date:
    return datetime.now(_SHANGHAI).date()


def _fill_known_cpi_gaps(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """补齐已知官方缺口月（如 2025-10）。"""
    by_period = {str(r["period"]): r for r in records if r.get("period")}
    for period, yoy in _CPI_GAP_YOY.items():
        existing = by_period.get(period)
        if existing is None or existing.get("cpi_yoy") is None:
            by_period[period] = {"period": period, "cpi_yoy": yoy}
    return [by_period[k] for k in sorted(by_period)]


def _normalize_cpi_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """统一为 {period, cpi_yoy}，过滤未来占位。"""
    today = _today_shanghai().isoformat()
    out: list[dict[str, Any]] = []
    for row in rows:
        period = row.get("period")
        value = row.get("cpi_yoy")
        if not period or value is None:
            continue
        release = row.get("cpi_release_date")
        # 未来发布占位（无现值或发布日在未来）一律丢弃
        if release and release > today:
            continue
        out.append(
            {
                "period": period,
                "cpi_yoy": round(float(value), 4),
            }
        )
    out.sort(key=lambda r: r["period"])
    return _fill_known_cpi_gaps(out)


def fetch_cpi_eastmoney() -> SourceFetchResult:
    """AKShare macro_usa_cpi_yoy → 东方财富美国 CPI 年率。"""
    df = safe_retry_df("macro_usa_cpi_yoy", ak.macro_usa_cpi_yoy, logger=logger)
    if df is None or df.empty:
        return SourceFetchResult.failure("东方财富 CPI：空结果")

    rows: list[dict[str, Any]] = []
    for _, raw in df.iterrows():
        period = parse_period(raw.get("时间") or raw.get("日期"))
        value = to_float(raw.get("现值"))
        release = parse_iso_date(raw.get("发布日期"))
        if not period:
            continue
        rows.append(
            {
                "period": period,
                "cpi_yoy": value,
                "cpi_release_date": release,
            }
        )
    records = _normalize_cpi_rows(rows)
    if not records:
        return SourceFetchResult.failure("东方财富 CPI：无有效已发布数据")
    return SourceFetchResult(records=records, ok=True)


def _bls_yoy_from_index(points: dict[str, float]) -> list[dict[str, Any]]:
    """未季调指数按年月键计算同比；跳过缺上年同月的点。"""
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


def fetch_cpi_bls(*, start_year: int = 2008) -> SourceFetchResult:
    """BLS Public API CUUR0000SA0 未季调指数 → 同比。"""
    end_year = _today_shanghai().year
    # 无 key 每次最多 10 年，按窗口分段拉取
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
            payload = http_get_json(url, label=f"bls_cpi_{year}_{window_end}")
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

    rows = _bls_yoy_from_index(points)
    records = _normalize_cpi_rows(rows)
    if not records:
        msg = "; ".join(errors[:3]) if errors else "BLS CPI：无有效数据"
        return SourceFetchResult.failure(msg)
    fr = SourceFetchResult(records=records, ok=True)
    if errors:
        fr.errors.extend(errors)
    return fr


def fetch_cpi() -> SourceFetchResult:
    """CPI：东财主源，失败/空/明显滞后时回退 BLS。"""
    primary = fetch_cpi_eastmoney()
    expected_lag_ok = False
    if primary.ok and primary.records:
        latest = primary.records[-1]["period"]
        # 主源最新月份距今不超过 3 个自然月视为可用
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
            logger.info(
                "CPI 使用 BLS 备源（主源错误: %s）",
                primary.error_summary(),
            )
        return fallback
    # 双源失败：若主源仍有旧数据则返回主源（部分可用）
    if primary.records:
        primary.ok = False
        primary.errors.append(fallback.error_summary() or "BLS 回退失败")
        return primary
    return SourceFetchResult.failure(
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
