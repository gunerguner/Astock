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
  sh_amount: number | null;
  sz_amount: number | null;
  turnover: number | null;
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
  name: string | null;
  amount: number | null;
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

export interface AssetPriceLevelItem {
  ticker: string;
  name: string;
  asset_type: 'stock' | 'metal';
  current_price: number | null;
  all_time_high: number | null;
  ath_date: string | null;
  percentage_diff: number | null;
  ath_days: number | null;
  daily_change: number | null;
  weekly_change: number | null;
  conclusion: string;
  data_pending?: boolean;
}

export interface AssetPriceLevels {
  last_synced_at: string | null;
  as_of: string;
  latest_trading_date: string | null;
  items: AssetPriceLevelItem[];
  cache_errors?: string[] | null;
}

export function fetchAssetPriceLevels(
  forceRefresh = false
): Promise<AssetPriceLevels> {
  return request.get('/analysis/asset-price-levels', {
    params: { force_refresh: forceRefresh || undefined },
  });
}

export interface MarketOverviewItem {
  key: string;
  name: string;
  code: string;
  current_price: number | null;
  daily_change: number | null;
  weekly_change: number | null;
  period_start: string | null;
  period_end: string | null;
  error: string | null;
}

export interface MarketOverviewCategory {
  key: string;
  name: string;
  items: MarketOverviewItem[];
}

export interface MarketOverview {
  as_of: string;
  latest_trading_date: string | null;
  categories: MarketOverviewCategory[];
  errors?: string[] | null;
}

export function fetchMarketOverview(
  forceRefresh = false
): Promise<MarketOverview> {
  return request.get('/analysis/market-overview', {
    params: { force_refresh: forceRefresh || undefined },
  });
}
