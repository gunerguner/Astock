import request from './request';

export interface BullMarketItem {
  market: string;
  start: string;
  end: string;
  description?: string | null;
  days: number;
  max_value: number | null;
}

export interface BullMarketStats {
  threshold: number;
  items: BullMarketItem[];
  total_days: number;
}

export interface TurnoverRankingItem {
  rank: number;
  date: string;
  sh_amount: number;
  sz_amount: number;
  turnover: number;
}

export interface TurnoverRanking {
  top: number;
  bull_market: string | null;
  items: TurnoverRankingItem[];
}

export interface StockRankingItem {
  rank: number;
  date: string;
  code: string;
  name: string;
  amount: number;
}

export interface StockRanking {
  top: number;
  bull_market: string | null;
  items: StockRankingItem[];
}

export function fetchBullMarketPointStats(
  threshold: number
): Promise<BullMarketStats> {
  return request.get('/analysis/bull-markets/point', {
    params: { threshold },
  });
}

export function fetchBullMarketTurnoverStats(
  threshold: number
): Promise<BullMarketStats> {
  return request.get('/analysis/bull-markets/turnover', {
    params: { threshold },
  });
}

export function fetchTurnoverRanking(
  top: number,
  bullMarket?: string
): Promise<TurnoverRanking> {
  return request.get('/analysis/turnover/ranking', {
    params: {
      top,
      bull_market: bullMarket && bullMarket !== 'all' ? bullMarket : undefined,
    },
  });
}

export function fetchStockRanking(
  top: number,
  bullMarket?: string
): Promise<StockRanking> {
  return request.get('/analysis/stock/ranking', {
    params: {
      top,
      bull_market: bullMarket && bullMarket !== 'all' ? bullMarket : undefined,
    },
  });
}

export interface PriceLevelPendingItem {
  ticker: string;
  name: string;
  asset_type: 'stock' | 'metal';
  conclusion: string;
  data_pending: true;
}

export interface PriceLevelDataItem {
  ticker: string;
  name: string;
  asset_type: 'stock' | 'metal';
  current_price: number;
  all_time_high: number;
  ath_date: string;
  percentage_diff: number;
  ath_days: number;
  daily_change: number | null;
  weekly_change: number | null;
  conclusion: string;
}

export type PriceLevelRow = PriceLevelDataItem | PriceLevelPendingItem;

export function isPriceLevelPending(
  item: PriceLevelRow
): item is PriceLevelPendingItem {
  return 'data_pending' in item && item.data_pending === true;
}

export interface AssetPriceLevels {
  last_synced_at: string | null;
  as_of: string;
  latest_trading_date: string;
  items: PriceLevelRow[];
  cache_errors?: string[];
}

export function fetchAssetPriceLevels(
  forceRefresh = false
): Promise<AssetPriceLevels> {
  return request.get('/analysis/asset-price-levels', {
    params: { force_refresh: forceRefresh || undefined },
  });
}

export interface MarketOverviewErrorItem {
  key: string;
  name: string;
  code: string;
  error: string;
}

export interface MarketOverviewDataItem {
  key: string;
  name: string;
  code: string;
  current_price: number;
  daily_change: number | null;
  weekly_change: number | null;
  period_start: string | null;
  period_end: string | null;
}

export type MarketOverviewRow =
  | MarketOverviewDataItem
  | MarketOverviewErrorItem;

export function isMarketOverviewError(
  item: MarketOverviewRow
): item is MarketOverviewErrorItem {
  return 'error' in item;
}

export interface MarketOverviewCategory {
  key: string;
  name: string;
  items: MarketOverviewRow[];
}

export interface MarketOverview {
  as_of: string;
  latest_trading_date: string;
  categories: MarketOverviewCategory[];
  errors?: string[];
}

export function fetchMarketOverview(
  forceRefresh = false
): Promise<MarketOverview> {
  return request.get('/analysis/market-overview', {
    params: { force_refresh: forceRefresh || undefined },
  });
}
