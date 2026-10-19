"""外盘期货近期收盘价。"""


from astock.datasets.market_overview.common import tail_closes
from astock.providers._shared.parsing import to_float
from astock.providers.akshare.assets import fetch_commodity_history


def fetch_foreign_futures(code: str, n: int) -> dict[str, float]:
    df = fetch_commodity_history(code)
    if df.empty:
        return {}
    pairs: list[tuple[str, float]] = []
    for _, row in df.iterrows():
        close = to_float(row.get("close"))
        if close is None:
            continue
        pairs.append((str(row.get("date")), close))
    return tail_closes(pairs, n, market="us")
