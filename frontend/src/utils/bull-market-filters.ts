import { DEFAULT_POINT_THRESHOLDS, POINT_INDEX_CODES } from '@/api/analysis';

export const BULL_MARKET_FILTER_STORAGE_KEY = 'astock.bull-market.filters';

export const DEFAULT_TURNOVER_THRESHOLD_TRILLION = 2;

const POINT_THRESHOLD_MAX = 10_000_000;
const TURNOVER_THRESHOLD_MAX = 10_000;

export interface BullMarketFilters {
  pointThresholds: API.PointThresholds;
  turnoverThresholdTrillion: number;
}

type FilterSource = Record<string, unknown>;

export function defaultBullMarketFilters(): BullMarketFilters {
  return {
    pointThresholds: { ...DEFAULT_POINT_THRESHOLDS },
    turnoverThresholdTrillion: DEFAULT_TURNOVER_THRESHOLD_TRILLION,
  };
}

function readStoredNumber(source: FilterSource, key: string): unknown {
  const nested = source.pointThresholds;
  if (!nested || typeof nested !== 'object' || Array.isArray(nested)) {
    return undefined;
  }
  return (nested as FilterSource)[key];
}

export function isPointThreshold(value: unknown): value is number {
  const numeric = typeof value === 'number' ? value : Number(value);
  return (
    Number.isInteger(numeric) && numeric >= 1 && numeric <= POINT_THRESHOLD_MAX
  );
}

export function isTurnoverThreshold(value: unknown): value is number {
  const numeric = typeof value === 'number' ? value : Number(value);
  return (
    Number.isFinite(numeric) &&
    numeric >= 0.01 &&
    numeric <= TURNOVER_THRESHOLD_MAX
  );
}

function roundTurnover(value: number): number {
  return Math.round(value * 100) / 100;
}

/** 非法字段回退到默认值。 */
export function coerceBullMarketFilters(source: object): BullMarketFilters {
  const record = source as FilterSource;
  const defaults = defaultBullMarketFilters();
  const pointThresholds = { ...defaults.pointThresholds };
  POINT_INDEX_CODES.forEach((code) => {
    const value = readStoredNumber(record, code);
    if (isPointThreshold(value)) {
      pointThresholds[code] = Number(value);
    }
  });
  const { turnoverThresholdTrillion } = record;
  return {
    pointThresholds,
    turnoverThresholdTrillion: isTurnoverThreshold(turnoverThresholdTrillion)
      ? roundTurnover(Number(turnoverThresholdTrillion))
      : defaults.turnoverThresholdTrillion,
  };
}

/** 表单里有空值或非法值时返回 null，避免静默改回默认阈值再查询。 */
export function snapshotBullMarketFilters(form: {
  pointThresholds: Partial<
    Record<(typeof POINT_INDEX_CODES)[number], number | null | undefined>
  >;
  turnoverThresholdTrillion: number | null | undefined;
}): BullMarketFilters | null {
  const pointThresholds = {} as API.PointThresholds;
  const invalidPoint = POINT_INDEX_CODES.some((code) => {
    const value = form.pointThresholds[code];
    if (!isPointThreshold(value)) return true;
    pointThresholds[code] = value;
    return false;
  });
  if (invalidPoint || !isTurnoverThreshold(form.turnoverThresholdTrillion)) {
    return null;
  }
  return {
    pointThresholds,
    turnoverThresholdTrillion: roundTurnover(form.turnoverThresholdTrillion),
  };
}

export function readStoredBullMarketFilters(
  storage: Pick<Storage, 'getItem'>,
): BullMarketFilters | null {
  try {
    const raw = storage.getItem(BULL_MARKET_FILTER_STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return null;
    }
    return coerceBullMarketFilters(parsed);
  } catch {
    return null;
  }
}

export function writeStoredBullMarketFilters(
  storage: Pick<Storage, 'setItem'>,
  filters: BullMarketFilters,
) {
  storage.setItem(BULL_MARKET_FILTER_STORAGE_KEY, JSON.stringify(filters));
}

export function resolveBullMarketFilters(
  storage: Pick<Storage, 'getItem'>,
): BullMarketFilters {
  return readStoredBullMarketFilters(storage) ?? defaultBullMarketFilters();
}
