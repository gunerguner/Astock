import { describe, expect, test } from 'vitest';
import { DEFAULT_POINT_THRESHOLDS } from '@/api/analysis';
import {
  BULL_MARKET_FILTER_STORAGE_KEY,
  readStoredBullMarketFilters,
  resolveBullMarketFilters,
  snapshotBullMarketFilters,
  writeStoredBullMarketFilters,
} from '@/utils/bull-market-filters';

function memoryStorage(initial = ''): Storage {
  const data = new Map<string, string>();
  if (initial) data.set(BULL_MARKET_FILTER_STORAGE_KEY, initial);
  return {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => {
      data.set(key, value);
    },
  } as Storage;
}

describe('bull market filters', () => {
  test('restores saved thresholds and falls back to defaults', () => {
    const storage = memoryStorage(
      JSON.stringify({
        pointThresholds: { ...DEFAULT_POINT_THRESHOLDS, '399006': 2800 },
        turnoverThresholdTrillion: 1.8,
      }),
    );
    const resolved = resolveBullMarketFilters(storage);
    expect(resolved.pointThresholds['399006']).toBe(2800);
    expect(resolved.turnoverThresholdTrillion).toBe(1.8);
    expect(resolveBullMarketFilters(memoryStorage())).toEqual({
      pointThresholds: { ...DEFAULT_POINT_THRESHOLDS },
      turnoverThresholdTrillion: 2,
    });
  });

  test('drops invalid stored values back to defaults', () => {
    const storage = memoryStorage(
      JSON.stringify({
        pointThresholds: { ...DEFAULT_POINT_THRESHOLDS, '000001': 0 },
        turnoverThresholdTrillion: 'nope',
      }),
    );
    const resolved = resolveBullMarketFilters(storage);
    expect(resolved.pointThresholds['000001']).toBe(
      DEFAULT_POINT_THRESHOLDS['000001'],
    );
    expect(resolved.turnoverThresholdTrillion).toBe(2);
  });

  test('rejects an incomplete form instead of querying defaults', () => {
    expect(
      snapshotBullMarketFilters({
        pointThresholds: { ...DEFAULT_POINT_THRESHOLDS, '000001': undefined },
        turnoverThresholdTrillion: 2,
      }),
    ).toBeNull();
  });

  test('round-trips a valid snapshot through storage', () => {
    const storage = memoryStorage();
    const snapshot = snapshotBullMarketFilters({
      pointThresholds: { ...DEFAULT_POINT_THRESHOLDS, '000300': 4600 },
      turnoverThresholdTrillion: 2.2,
    });
    expect(snapshot).not.toBeNull();
    if (!snapshot) return;
    writeStoredBullMarketFilters(storage, snapshot);
    expect(readStoredBullMarketFilters(storage)).toEqual(snapshot);
  });
});
