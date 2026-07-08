"""全球资产价格水位查询（读路径）。"""

from datetime import date

from sqlmodel import Session, select

from astock.config import GLOBAL_ASSETS
from astock.core.datetime_utils import iso_now, now_local
from astock.core.exceptions import AppError
from astock.core.redis_client import LATEST_TRADING_DATE_KEY, get_string, set_string
from astock.models.asset_high import AssetHigh
from astock.schemas.analysis import (
    PriceLevelItem,
    PriceLevelPendingItem,
    PriceLevelsResponse,
)
from astock.services.global_asset._cache import (
    backfill_from_akshare,
    conclusion,
    pending_item,
    read_price_cache,
)
from astock.services.price_utils import baseline_prices, pct_change, sorted_dates
from astock.services.sync_store import get_sync_meta


def _ensure_price_cache(
    assets: list[dict[str, str]], *, force_refresh: bool = False
) -> tuple[dict[str, dict[str, float]], list[str]]:
    if not force_refresh:
        all_closes: dict[str, dict[str, float]] = {}
        missing: list[dict[str, str]] = []
        for asset in assets:
            ticker = asset["ticker"]
            closes = read_price_cache(ticker)
            if closes:
                all_closes[ticker] = closes
            else:
                missing.append(asset)
        if not missing:
            latest = get_string(LATEST_TRADING_DATE_KEY)
            if latest is None:
                from astock.services.price_utils import latest_trading_date

                latest = latest_trading_date(all_closes)
                if latest:
                    set_string(LATEST_TRADING_DATE_KEY, latest)
            return all_closes, []
        backfill, errors = backfill_from_akshare(missing)
        all_closes.update(backfill)
        return all_closes, errors

    return backfill_from_akshare(assets)


def get_price_levels(db: Session, *, force_refresh: bool = False) -> PriceLevelsResponse:
    rows = db.exec(select(AssetHigh)).all()
    if not rows and not force_refresh:
        meta = get_sync_meta(db, "asset_high")
        if meta is None:
            raise ValueError("全球资产历史最高点数据为空，请先刷新数据")

    all_closes, cache_errors = _ensure_price_cache(GLOBAL_ASSETS, force_refresh=force_refresh)

    row_map = {row.ticker: row for row in rows}
    items: list[PriceLevelItem | PriceLevelPendingItem] = []
    now = now_local()
    as_of = iso_now()

    for asset in GLOBAL_ASSETS:
        ticker = asset["ticker"]
        closes = all_closes.get(ticker, {})
        current, prev_close, week_ago_close = baseline_prices(closes)
        if current is None:
            if asset.get("data_pending"):
                items.append(pending_item(asset))
            else:
                cache_errors.append(f"{ticker}: 当前价格缺失")
            continue

        row = row_map.get(ticker)
        if row is None:
            cache_errors.append(f"{ticker}: 数据库无 ATH 记录，请先刷新导入")
            continue

        all_time_high = float(row.all_time_high)
        ath_date = row.ath_date
        if current > all_time_high:
            all_time_high = current
            ath_date = sorted_dates(closes)[-1] if closes else ath_date

        percentage_diff = (current - all_time_high) / all_time_high * 100
        try:
            ath_days = (now.date() - date.fromisoformat(ath_date)).days
        except ValueError:
            ath_days = 0

        items.append(
            PriceLevelItem(
                ticker=ticker,
                name=row.name,
                asset_type=row.asset_type,
                current_price=round(current, 4),
                all_time_high=round(all_time_high, 4),
                ath_date=ath_date,
                percentage_diff=round(percentage_diff, 2),
                ath_days=ath_days,
                daily_change=round(v, 2)
                if (v := pct_change(current, prev_close)) is not None
                else None,
                weekly_change=round(v, 2)
                if (v := pct_change(current, week_ago_close)) is not None
                else None,
                conclusion=conclusion(percentage_diff),
            )
        )

    items.sort(
        key=lambda x: (
            0 if isinstance(x, PriceLevelPendingItem) else 1,
            x.percentage_diff if isinstance(x, PriceLevelItem) else 0,
        )
    )

    meta = get_sync_meta(db, "asset_high")
    latest_trading_date_value = get_string(LATEST_TRADING_DATE_KEY) or (
        meta.last_synced_date if meta else None
    )
    if latest_trading_date_value is None:
        raise AppError("无法确定最新交易日，请先刷新全球资产数据")

    return PriceLevelsResponse(
        last_synced_at=meta.last_synced_at if meta else None,
        as_of=as_of,
        latest_trading_date=latest_trading_date_value,
        items=items,
        cache_errors=cache_errors[:5] if cache_errors else None,
    )
