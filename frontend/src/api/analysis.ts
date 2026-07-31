import request from './request';

export const POINT_INDEX_CODES = [
  '000001',
  '000300',
  '399006',
  '000688',
] as const;

export const DEFAULT_POINT_THRESHOLDS: API.PointThresholds = {
  '000001': 4000,
  '000300': 4500,
  '399006': 2500,
  '000688': 1200,
};

export function isPriceLevelPending(
  item: API.PriceLevelRow,
): item is API.PriceLevelPendingItem {
  return 'data_pending' in item && item.data_pending === true;
}

export function isMarketOverviewError(
  item: API.MarketOverviewRow,
): item is API.MarketOverviewErrorItem {
  return 'error' in item;
}

/** 获取多指数牛市点位达标统计 GET /analysis/bull-markets/point */
export function fetchBullMarketPointStats(
  thresholds: API.PointThresholds,
): Promise<API.MultiIndexPointStats> {
  return request.get('/analysis/bull-markets/point', {
    params: {
      threshold_000001: thresholds['000001'],
      threshold_000300: thresholds['000300'],
      threshold_399006: thresholds['399006'],
      threshold_000688: thresholds['000688'],
    },
  });
}

/** 获取牛市成交额达标统计 GET /analysis/bull-markets/turnover */
export function fetchBullMarketTurnoverStats(
  threshold: number,
): Promise<API.BullMarketStats> {
  return request.get('/analysis/bull-markets/turnover', {
    params: { threshold },
  });
}

/** 获取大盘成交额 TopN GET /analysis/turnover/ranking */
export function fetchTurnoverRanking(
  top: number,
): Promise<API.TurnoverRanking> {
  return request.get('/analysis/turnover/ranking', {
    params: { top },
  });
}

/** 获取个股成交额 TopN GET /analysis/stock/ranking */
export function fetchStockRanking(top: number): Promise<API.StockRanking> {
  return request.get('/analysis/stock/ranking', {
    params: { top },
  });
}

/** 获取全球资产价格水位 GET /analysis/asset-price-levels */
export function fetchAssetPriceLevels(
  forceRefresh = false,
): Promise<API.AssetPriceLevels> {
  return request.get('/analysis/asset-price-levels', {
    params: { force_refresh: forceRefresh || undefined },
  });
}

/** 获取全球市场概览 GET /analysis/market-overview */
export function fetchMarketOverview(
  forceRefresh = false,
): Promise<API.MarketOverview> {
  return request.get('/analysis/market-overview', {
    params: { force_refresh: forceRefresh || undefined },
  });
}

/** 获取美国宏观月度序列 GET /analysis/us-macro */
export function fetchUsMacroData(start = '2020-06'): Promise<API.UsMacroData> {
  return request.get('/analysis/us-macro', {
    params: { start },
  });
}

/** 获取中国宏观月度序列 GET /analysis/cn-macro */
export function fetchCnMacroData(start?: string): Promise<API.CnMacroData> {
  return request.get('/analysis/cn-macro', {
    params: start ? { start } : undefined,
  });
}
