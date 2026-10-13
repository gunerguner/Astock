import { beforeEach, describe, expect, test, vi } from 'vitest';

import {
  DEFAULT_POINT_THRESHOLDS,
  POINT_INDEX_CODES,
  fetchAssetPriceLevels,
  fetchBullMarketPointStats,
  fetchBullMarketTurnoverStats,
  fetchCnMacroData,
  fetchMarketOverview,
  fetchStockRanking,
  fetchTurnoverRanking,
  fetchUsMacroData,
  isMarketOverviewError,
  isPriceLevelPending,
} from '@/api/analysis';

const { getMock } = vi.hoisted(() => ({ getMock: vi.fn() }));

vi.mock('@/api/request', () => ({ default: { get: getMock, post: vi.fn() } }));

beforeEach(() => {
  getMock.mockReset();
  getMock.mockResolvedValue(null);
});

describe('契约常量(与后端配置联动)', () => {
  test('指数代码与默认阈值', () => {
    expect(POINT_INDEX_CODES).toEqual(['000001', '000300', '399006', '000688']);
    expect(DEFAULT_POINT_THRESHOLDS).toEqual({
      '000001': 4000,
      '000300': 4500,
      '399006': 2500,
      '000688': 1200,
    });
  });
});

describe('URL 与参数构造', () => {
  test('牛市点位统计:四个阈值全部作为 query', async () => {
    await fetchBullMarketPointStats({
      '000001': 4000,
      '000300': 4500,
      '399006': 2500,
      '000688': 1200,
    });
    expect(getMock).toHaveBeenCalledWith('/analysis/bull-markets/point', {
      params: {
        threshold_000001: 4000,
        threshold_000300: 4500,
        threshold_399006: 2500,
        threshold_000688: 1200,
      },
    });
  });

  test('牛市成交额统计', async () => {
    await fetchBullMarketTurnoverStats(2e12);
    expect(getMock).toHaveBeenCalledWith('/analysis/bull-markets/turnover', {
      params: { threshold: 2e12 },
    });
  });

  test('大盘/个股成交额 TopN', async () => {
    await fetchTurnoverRanking(20);
    expect(getMock).toHaveBeenCalledWith('/analysis/turnover/ranking', {
      params: { top: 20 },
    });

    await fetchStockRanking(10);
    expect(getMock).toHaveBeenCalledWith('/analysis/stock/ranking', {
      params: { top: 10 },
    });
  });

  test('全球资产/市场概览:false 时 force_refresh 不出现在 query', async () => {
    await fetchAssetPriceLevels();
    expect(getMock).toHaveBeenCalledWith('/analysis/asset-price-levels', {
      params: { force_refresh: undefined },
    });

    await fetchMarketOverview(true);
    expect(getMock).toHaveBeenCalledWith('/analysis/market-overview', {
      params: { force_refresh: true },
    });
  });

  test('中美宏观无 start 时不带 query', async () => {
    await fetchUsMacroData();
    expect(getMock).toHaveBeenCalledWith('/analysis/us-macro', {
      params: undefined,
    });

    await fetchUsMacroData('2020-06');
    expect(getMock).toHaveBeenCalledWith('/analysis/us-macro', {
      params: { start: '2020-06' },
    });

    await fetchCnMacroData();
    expect(getMock).toHaveBeenCalledWith('/analysis/cn-macro', {
      params: undefined,
    });

    await fetchCnMacroData('2022-01');
    expect(getMock).toHaveBeenCalledWith('/analysis/cn-macro', {
      params: { start: '2022-01' },
    });
  });
});

describe('联合类型守卫', () => {
  test('isPriceLevelPending 仅认 data_pending=true', () => {
    const pending = {
      ticker: 'SPCX',
      name: 'SpaceX',
      asset_type: 'stock',
      conclusion: 'pending',
      data_pending: true,
    } satisfies API.PriceLevelPendingItem;
    const normal = {
      ticker: 'AAPL',
      name: '苹果',
      asset_type: 'stock',
      current_price: 250,
      all_time_high: 300,
      ath_date: '2024-12-16',
      percentage_diff: -16.67,
      ath_days: 100,
      daily_change: null,
      weekly_change: null,
      conclusion: 'moderatePullback',
    } satisfies API.PriceLevelDataItem;
    expect(isPriceLevelPending(pending)).toBe(true);
    expect(isPriceLevelPending(normal)).toBe(false);
  });

  test('isMarketOverviewError 仅认 error 字段', () => {
    const errorItem = {
      key: 'k',
      name: 'n',
      code: 'c',
      error: '数据获取失败',
    } satisfies API.MarketOverviewErrorItem;
    const normal = {
      key: 'k',
      name: 'n',
      code: 'c',
      current_price: 1,
      daily_change: null,
      weekly_change: null,
      period_start: 'd1',
      period_end: 'd2',
    } satisfies API.MarketOverviewDataItem;
    expect(isMarketOverviewError(errorItem)).toBe(true);
    expect(isMarketOverviewError(normal)).toBe(false);
  });
});
