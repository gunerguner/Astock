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
