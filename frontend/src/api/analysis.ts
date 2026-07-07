import axios from 'axios';

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

export function fetchBullMarketPointStats(threshold: number) {
  return axios.get<BullMarketStats>('/analysis/bull-markets/point', {
    params: { threshold },
  });
}

export function fetchBullMarketTurnoverStats(threshold: number) {
  return axios.get<BullMarketStats>('/analysis/bull-markets/turnover', {
    params: { threshold },
  });
}

export function fetchTurnoverRanking(top: number, bullMarket?: string) {
  return axios.get<TurnoverRanking>('/analysis/turnover/ranking', {
    params: {
      top,
      bull_market: bullMarket && bullMarket !== 'all' ? bullMarket : undefined,
    },
  });
}

export function fetchStockRanking(top: number, bullMarket?: string) {
  return axios.get<StockRanking>('/analysis/stock/ranking', {
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

export function fetchAssetPriceLevels(forceRefresh = false) {
  return axios.get<AssetPriceLevels>('/analysis/asset-price-levels', {
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

export function fetchMarketOverview(forceRefresh = false) {
  return axios.get<MarketOverview>('/analysis/market-overview', {
    params: { force_refresh: forceRefresh || undefined },
  });
}
