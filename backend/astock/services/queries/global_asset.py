"""全球资产价格水位查询（读路径）。"""

from datetime import date

from fastapi import status
from sqlmodel import Session, select

from astock.config import ASSET_PRICE_CACHE_TTL, GLOBAL_ASSETS, GlobalAssetConfig
from astock.core.datetime_utils import (
    filter_settled_closes,
    iso_now,
    last_settled_date,
    market_for_asset_type,
    now_local,
)
from astock.core.errors import AppError, ErrorCode
from astock.core.price_utils import (
    anchor_date_for_closes,
    resolve_latest_trading_date,
    sorted_dates,
)
from astock.core.redis_client import redis_gateway
from astock.models.asset_high import AssetHigh
from astock.schemas.analysis import (
    PriceLevelItem,
    PriceLevelPendingItem,
    PriceLevelsResponse,
)
from astock.services.cache.asset_prices import (
    backfill_from_akshare,
    conclusion,
    global_asset_markets,
    pending_item,
    read_price_cache,
    write_price_cache,
)
from astock.services.cache.closes import (
    ClosesCacheDeps,
    ClosesEnsureOptions,
    ClosesFetchResult,
    build_change_fields,
    ensure_closes,
)
from astock.services.cache.keys import LATEST_TRADING_DATE_KEY
from astock.services.sync.store import get_sync_meta

_PRICE_CACHE_DEPS = ClosesCacheDeps(
    key_fn=lambda a: a["ticker"],
    market_fn=lambda a: market_for_asset_type(a["asset_type"]),
    read_closes=lambda ticker, market: read_price_cache(ticker, market=market),
    write_closes=lambda ticker, closes, market: write_price_cache(ticker, closes, market=market),
    fetch_missing=backfill_from_akshare,
    latest_date_key=LATEST_TRADING_DATE_KEY,
    latest_ttl=ASSET_PRICE_CACHE_TTL,
)


def _ensure_price_cache(
    assets: list[GlobalAssetConfig], *, force_refresh: bool = False
) -> ClosesFetchResult:
    """确保全球资产收盘价缓存齐全，缺失时通过 AkShare 回填。"""
    return ensure_closes(
        assets,
        _PRICE_CACHE_DEPS,
        ClosesEnsureOptions(force_refresh=force_refresh),
    )


def _append_missing_price(
    asset: GlobalAssetConfig,
    *,
    items: list[PriceLevelItem | PriceLevelPendingItem],
    cache_errors: list[str],
) -> None:
    if asset.get("data_pending"):
        items.append(pending_item(asset))
    else:
        cache_errors.append(f"{asset['ticker']}: 当前价格缺失")


def get_price_levels(db: Session, *, force_refresh: bool = False) -> PriceLevelsResponse:
    """查询全球资产相对历史最高点的价格水位与日/周涨跌。"""
    rows = db.exec(select(AssetHigh)).all()
    meta = get_sync_meta(db, "asset_high")
    if not rows and not force_refresh and meta is None:
        raise AppError(
            message="全球资产历史最高点数据为空，请先刷新数据",
            code=ErrorCode.VALIDATION_ERROR,
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    fetched = _ensure_price_cache(GLOBAL_ASSETS, force_refresh=force_refresh)
    all_closes = fetched.closes
    cache_errors = list(fetched.errors)

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
        if anchor is None:
            _append_missing_price(asset, items=items, cache_errors=cache_errors)
            continue

        fields = build_change_fields(closes, anchor)
        current = fields.current
        if current is None:
            _append_missing_price(asset, items=items, cache_errors=cache_errors)
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
                current_price=fields.current_price,
                all_time_high=round(all_time_high, 4),
                ath_date=ath_date,
                percentage_diff=round(percentage_diff, 2),
                ath_days=ath_days,
                daily_change=fields.daily_change,
                weekly_change=fields.weekly_change,
                conclusion=conclusion(percentage_diff),
            )
        )

    items.sort(
        key=lambda x: (
            0 if isinstance(x, PriceLevelPendingItem) else 1,
            x.percentage_diff if isinstance(x, PriceLevelItem) else 0,
        )
    )

    settled_closes = {
        ticker: filter_settled_closes(closes, asset_markets[ticker])
        for ticker, closes in all_closes.items()
        if ticker in asset_markets
    }
    latest_trading_date_value = resolve_latest_trading_date(
        settled_closes,
        markets=asset_markets,
        redis_fallback=redis_gateway.get_string(LATEST_TRADING_DATE_KEY),
        meta_fallback=meta.last_synced_date if meta else None,
        display_cap=max(last_settled_date("cn"), last_settled_date("us")),
    )
    if latest_trading_date_value is None:
        raise AppError(message="无法确定最新交易日，请先刷新全球资产数据")

    return PriceLevelsResponse(
        last_synced_at=meta.last_synced_at if meta else None,
        as_of=as_of,
        latest_trading_date=latest_trading_date_value,
        items=items,
        cache_errors=cache_errors[:5],
    )
