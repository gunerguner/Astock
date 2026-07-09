"""全球资产价格水位查询（读路径）。"""

from datetime import date

from sqlmodel import Session, select

from astock.config import GLOBAL_ASSETS
from astock.core.datetime_utils import filter_settled_closes, iso_now, last_settled_date, market_for_asset_type, now_local
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
from astock.services.price_utils import (
    anchor_date_excluding_today,
    anchor_date_for_closes,
    baseline_prices_at_anchor,
    baseline_prices,
    global_asset_markets,
    pct_change,
    sorted_dates,
)
from astock.services.sync_store import get_sync_meta


def _ensure_price_cache(
    assets: list[dict[str, str]], *, force_refresh: bool = False
) -> tuple[dict[str, dict[str, float]], list[str]]:
    if not force_refresh:
        all_closes: dict[str, dict[str, float]] = {}
        missing: list[dict[str, str]] = []
        for asset in assets:
            ticker = asset["ticker"]
            market = market_for_asset_type(asset["asset_type"])
            closes = read_price_cache(ticker, market=market)
            if closes:
                all_closes[ticker] = closes
            else:
                missing.append(asset)
        if not missing:
            latest = get_string(LATEST_TRADING_DATE_KEY)
            if latest is None:
                latest = anchor_date_excluding_today(
                    all_closes,
                    markets=global_asset_markets(assets),
                )
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

    asset_markets = global_asset_markets(GLOBAL_ASSETS)
    for asset in GLOBAL_ASSETS:
        ticker = asset["ticker"]
        market = asset_markets[ticker]
        closes = filter_settled_closes(all_closes.get(ticker, {}), market)
        anchor = anchor_date_for_closes(closes, market)
        current, prev_close, week_ago_close = (
            baseline_prices(closes)
            if anchor is None
            else baseline_prices_at_anchor(closes, anchor)
        )
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
    settled_closes = {
        ticker: filter_settled_closes(closes, asset_markets[ticker])
        for ticker, closes in all_closes.items()
        if ticker in asset_markets
    }
    latest_trading_date_value = (
        anchor_date_excluding_today(settled_closes, markets=asset_markets)
        or get_string(LATEST_TRADING_DATE_KEY)
        or (meta.last_synced_date if meta else None)
    )
    display_cap = max(last_settled_date("cn"), last_settled_date("us"))
    if latest_trading_date_value and latest_trading_date_value > display_cap:
        latest_trading_date_value = display_cap
    if latest_trading_date_value is None:
        raise AppError("无法确定最新交易日，请先刷新全球资产数据")

    return PriceLevelsResponse(
        last_synced_at=meta.last_synced_at if meta else None,
        as_of=as_of,
        latest_trading_date=latest_trading_date_value,
        items=items,
        cache_errors=cache_errors[:5] if cache_errors else None,
    )
