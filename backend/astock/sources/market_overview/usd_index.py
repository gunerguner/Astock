"""美元指数抓取：历史 + 现货合并。"""

from astock.config import WEEKLY_BASELINE_OFFSET
from astock.core.price_utils import anchor_date_for_closes
from astock.sources.market_overview._common import _merge_close_dicts
from astock.sources.market_overview.usd_index_history import fetch_usd_index_history
from astock.sources.market_overview.usd_index_spot import fetch_usd_index_spot


def fetch_usd_index(n: int) -> dict[str, float]:
    spot = fetch_usd_index_spot()

    required_points = WEEKLY_BASELINE_OFFSET
    history_n = max(n, required_points + 5)
    history = fetch_usd_index_history(history_n)
    if not spot and not history:
        return {}

    merged = _merge_close_dicts(history, spot, n=n, market="us")
    anchor = anchor_date_for_closes(merged, "us")
    if anchor is None:
        return merged
    dates = [d for d in sorted(merged.keys()) if d <= anchor]
    if len(dates) >= required_points:
        return merged

    if history:
        history = fetch_usd_index_history(history_n + 10)
        merged = _merge_close_dicts(history, spot, n=n, market="us")
    return merged
