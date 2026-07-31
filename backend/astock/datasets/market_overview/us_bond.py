"""美债收益率近期收盘价。"""


from astock.config import MARKET_OVERVIEW_RECENT_DAYS, US_BOND_COLUMNS
from astock.datasets.market_overview.common import df_to_tail_closes
from astock.providers.akshare.economics import fetch_bond_zh_us_rate


def fetch_us_bond_rates() -> dict[str, dict[str, float]]:
    """一次调用返回配置中的中美国债 recent_closes。"""
    df = fetch_bond_zh_us_rate()
    if df is None:
        return {}

    result: dict[str, dict[str, float]] = {}
    for code, col in US_BOND_COLUMNS.items():
        closes = df_to_tail_closes(
            df, MARKET_OVERVIEW_RECENT_DAYS, date_col="日期", value_col=col
        )
        if closes:
            result[code] = closes
    return result
