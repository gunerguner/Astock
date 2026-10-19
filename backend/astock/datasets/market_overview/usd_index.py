"""美元指数：日线历史为主，现货仅补最新结算日。"""


import logging
from datetime import datetime, timedelta

from astock.config import (
    EM_HIST_HOSTS,
    MARKET_OVERVIEW_RECENT_DAYS,
    WEEKLY_BASELINE_OFFSET,
)
from astock.core.datetime_utils import last_settled_date
from astock.core.price_utils import has_sufficient_baseline_points
from astock.datasets.market_overview.common import merge_close_dicts, tail_closes, df_to_tail_closes
from astock.providers.akshare.market import fetch_usd_index_hist_em
from astock.providers import eastmoney, sina
from astock.providers._shared.parsing import to_float

logger = logging.getLogger(__name__)


def _previous_weekday(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d").date() - timedelta(days=1)
    while dt.weekday() >= 5:
        dt -= timedelta(days=1)
    return dt.isoformat()


def _spot_pairs_to_closes(
    quote_date: str,
    current: float,
    prev: float | None,
) -> dict[str, float]:
    pairs: list[tuple[str, float]] = [(quote_date, current)]
    if prev is not None:
        pairs.insert(0, (_previous_weekday(quote_date), prev))
    return tail_closes(pairs, MARKET_OVERVIEW_RECENT_DAYS, market="us")


def _same_magnitude(raw: float, ref: float) -> bool:
    if ref == 0:
        return False
    ratio = raw / ref
    return 0.5 <= ratio <= 2.0


def _align_spot_quote(
    quote: dict,
    history: dict[str, float],
    *,
    hundredths: bool,
) -> tuple[dict[str, float], str | None]:
    """对照同日或最近一根 K 线决定现货是否乘 0.01。差一个数量级以上则不补点。"""
    current = to_float(quote.get("current"))
    prev_f = to_float(quote.get("prev"))
    if current is None:
        return {}, "美元指数现货价格无效"
    if not history:
        if hundredths:
            current *= 0.01
            if prev_f is not None:
                prev_f *= 0.01
        return _spot_pairs_to_closes(quote["quote_date"], current, prev_f), None

    ref_date = quote["quote_date"] if quote["quote_date"] in history else max(history)
    ref = history[ref_date]
    scale = 1.0
    if not _same_magnitude(current, ref):
        # em 现货按百分之一发布：缩放后数量级对得上才补点，否则放弃
        if hundredths and _same_magnitude(current * 0.01, ref):
            scale = 0.01
        else:
            return {}, (
                f"美元指数现货 {current} 与 K 线 {ref_date} 收盘 {ref} 数量级不一致，未补最新点"
            )
    scaled_prev = prev_f * scale if prev_f is not None else None
    return _spot_pairs_to_closes(quote["quote_date"], current * scale, scaled_prev), None


def _fetch_usd_index_spot(
    history: dict[str, float],
) -> tuple[dict[str, float], str | None]:
    errors: list[str] = []
    for fetcher, label, hundredths in (
        (sina.fetch_diniw_spot, "sina", False),
        (eastmoney.fetch_udi_spot, "em", True),
    ):
        try:
            quote = fetcher()
        except Exception as e:
            errors.append(f"{label}: {e}")
            logger.warning("美元指数现货失败(%s): %s", label, e)
            continue
        if not quote:
            errors.append(f"{label}: 空行情")
            continue
        closes, err = _align_spot_quote(quote, history, hundredths=hundredths)
        if err:
            errors.append(err)
            logger.warning(err)
            continue
        if closes:
            return closes, None
    return {}, "; ".join(errors) if errors else "美元指数现货为空"


def _fetch_usd_index_history_sina(n: int) -> dict[str, float]:
    pairs = sina.fetch_diniw_day_k()
    closes = tail_closes(pairs, n, market="us")
    if closes:
        logger.info("美元指数历史来自新浪 DINIW: %s 点", len(closes))
    return closes


def _fetch_usd_index_history_akshare(n: int) -> dict[str, float]:
    df = fetch_usd_index_hist_em()
    closes = df_to_tail_closes(df, n, date_col="日期", value_col="收盘", market="us")
    if closes:
        logger.info("美元指数历史来自 akshare: %s 点", len(closes))
    return closes


def _fetch_usd_index_history_em(host: str, n: int) -> dict[str, float]:
    pairs = eastmoney.fetch_udi_history(host, n)
    return tail_closes(pairs, n, market="us")


def _fetch_usd_index_history(n: int) -> tuple[dict[str, float], list[str]]:
    errors: list[str] = []
    for fetcher, label in (
        (_fetch_usd_index_history_sina, "sina"),
        (_fetch_usd_index_history_akshare, "akshare"),
    ):
        try:
            closes = fetcher(n)
            if closes:
                return closes, errors
            errors.append(f"{label}: 数据为空")
            logger.warning("美元指数历史(%s)数据为空", label)
        except Exception as e:
            errors.append(f"{label}: {e}")
            logger.warning("美元指数历史(%s)失败: %s", label, e)

    for host in EM_HIST_HOSTS:
        try:
            closes = _fetch_usd_index_history_em(host, n)
            if closes:
                logger.info("美元指数历史来自东财 %s: %s 点", host, len(closes))
                return closes, errors
            errors.append(f"{host}: 数据为空")
            logger.warning("美元指数历史(%s)数据为空", host)
        except Exception as e:
            errors.append(f"{host}: {e}")
            logger.warning("美元指数历史(%s)失败: %s", host, e)
    return {}, errors


def _needs_spot_patch(history: dict[str, float]) -> bool:
    if not history:
        return True
    if not has_sufficient_baseline_points(history, market="us"):
        return True
    return max(history) < last_settled_date("us")


def fetch_usd_index(n: int) -> dict[str, float]:
    """日线历史为主；现货仅在历史缺最新结算日或点数不足时补丁合并。"""
    required_points = WEEKLY_BASELINE_OFFSET
    history_n = max(n, required_points + 5)
    history, history_errors = _fetch_usd_index_history(history_n)

    spot: dict[str, float] = {}
    spot_error: str | None = None
    if _needs_spot_patch(history):
        spot, spot_error = _fetch_usd_index_spot(history)
        if spot_error and not spot:
            detail = "; ".join([*history_errors, spot_error])
            if not history:
                raise RuntimeError(detail)
            logger.warning("美元指数现货未并入: %s", detail)

    if not history and not spot:
        raise RuntimeError("; ".join(history_errors) or "美元指数数据为空")

    if not spot:
        return history

    merged = merge_close_dicts(history, spot, n=n, market="us")
    if has_sufficient_baseline_points(merged, market="us"):
        return merged

    longer, _longer_errors = _fetch_usd_index_history(history_n + 10)
    if longer:
        merged = merge_close_dicts(longer, spot, n=n, market="us")
    return merged
