"""A 股指数近期收盘价。"""


import pandas as pd

from astock.datasets.market_overview.common import cn_index_cutoff, tail_closes
from astock.providers._shared.symbols import cn_index_sina_symbol
from astock.providers._shared.parsing import to_float
from astock.providers.akshare.market import fetch_cn_index_daily


def fetch_cn_index(code: str, n: int) -> dict[str, float]:
    sina_symbol = cn_index_sina_symbol(code)
    cutoff = cn_index_cutoff()
    raw = fetch_cn_index_daily(sina_symbol)
    if raw is None or raw.empty:
        return {}
    df = raw.rename(columns={"date": "Date", "close": "Close"})
    if "Date" not in df.columns or "Close" not in df.columns:
        return {}
    df["Date"] = pd.to_datetime(df["Date"])
    indexed = df.set_index("Date").sort_index()
    indexed["Close"] = pd.to_numeric(indexed["Close"], errors="coerce")
    filtered = indexed.loc[indexed["Close"].notna()]
    window = filtered.loc[filtered.index >= pd.Timestamp(cutoff.date())]
    pairs: list[tuple[str, float]] = []
    for ts, row in window.iterrows():
        close = to_float(row["Close"])
        if close is None:
            continue
        pairs.append((str(ts)[:10], close))
    return tail_closes(pairs, n, market="cn")
