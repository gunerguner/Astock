import axios from 'axios';

export interface BullMarketMetaItem {
  name: string;
  start: string;
  end: string;
  description?: string | null;
}

export interface BullMarketsMeta {
  items: BullMarketMetaItem[];
}

export function fetchBullMarkets() {
  return axios.get<BullMarketsMeta>('/meta/bull-markets');
}
