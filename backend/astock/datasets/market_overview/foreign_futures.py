"""外盘期货近期收盘价。"""

from astock.datasets.market_overview.common import df_to_tail_closes
from astock.providers.akshare.assets import fetch_commodity_history


def fetch_foreign_futures(code: str, n: int) -> dict[str, float]:
    df = fetch_commodity_history(code)
    if df.empty:
        return {}
    return df_to_tail_closes(df, n, date_col="date", value_col="close", market="us")
