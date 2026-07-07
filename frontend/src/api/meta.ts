import request from './request';

export interface BullMarketMetaItem {
  name: string;
  start: string;
  end: string;
  description?: string | null;
}

export interface BullMarketsMeta {
  items: BullMarketMetaItem[];
}

export function fetchBullMarkets(): Promise<BullMarketsMeta> {
  return request.get('/meta/bull-markets');
}
