import { computed, reactive } from 'vue';
import { useI18n } from 'vue-i18n';
import {
  DEFAULT_POINT_THRESHOLDS,
  fetchBullMarketPointStats,
  fetchBullMarketTurnoverStats,
  POINT_INDEX_CODES,
  type BullMarketStats,
  type MultiIndexPointStats
} from '@/api/analysis';
import useAsyncRequest from '@/hooks/async-request';
import buildMergedColumns from './columns';

export const indexConfigs = [
  {
    code: '000001',
    nameKey: 'pages.bullMarket.indexSh',
    filterKey: 'pages.bullMarket.filterSh'
  },
  {
    code: '000300',
    nameKey: 'pages.bullMarket.indexHS300',
    filterKey: 'pages.bullMarket.filterHS300'
  },
  {
    code: '399006',
    nameKey: 'pages.bullMarket.indexCYB',
    filterKey: 'pages.bullMarket.filterCYB'
  },
  {
    code: '000688',
    nameKey: 'pages.bullMarket.indexKCB50',
    filterKey: 'pages.bullMarket.filterKCB50'
  }
] as const;

export type IndexConfig = (typeof indexConfigs)[number];

export interface IndexCell {
  days: number | null;
  max: number | null;
  notAvailable: boolean;
}

export interface MergedRow {
  market: string;
  start: string;
  end: string;
  description?: string | null;
  indices: Record<string, IndexCell>;
  turnoverDays: number | null;
  turnoverMax: number | null;
}

interface BullStatsPair {
  point: MultiIndexPointStats;
  turnover: BullMarketStats;
}

export default function useBullMarket() {
  const { t } = useI18n();

  const filterForm = reactive({
    pointThresholds: { ...DEFAULT_POINT_THRESHOLDS },
    turnoverThresholdTrillion: 2
  });

  const {
    loading,
    data: statsData,
    run: loadStats
  } = useAsyncRequest(async (): Promise<BullStatsPair> => {
    const [point, turnover] = await Promise.all([
      fetchBullMarketPointStats(filterForm.pointThresholds),
      fetchBullMarketTurnoverStats(filterForm.turnoverThresholdTrillion * 1e12)
    ]);
    return { point, turnover };
  });

  const pointStats = computed(() => statsData.value?.point ?? null);
  const turnoverStats = computed(() => statsData.value?.turnover ?? null);

  const pointStatsByIndex = computed(() => {
    const map = new Map(
      (pointStats.value?.indices ?? []).map((item) => [item.index_code, item])
    );
    return map;
  });

  const getIndexTotalDays = (indexCode: string) => {
    const stats = pointStatsByIndex.value.get(indexCode);
    return stats?.total_days ?? '-';
  };

  const mergedRows = computed<MergedRow[]>(() => {
    const base =
      pointStats.value?.indices[0]?.items ?? turnoverStats.value?.items ?? [];
    const turnoverByMarket = new Map(
      (turnoverStats.value?.items ?? []).map((item) => [item.market, item])
    );

    return base.map((item) => {
      const turnoverItem = turnoverByMarket.get(item.market);
      const indices = Object.fromEntries(
        POINT_INDEX_CODES.map((code) => {
          const indexItem = pointStatsByIndex.value
            .get(code)
            ?.items.find((entry) => entry.market === item.market);
          return [
            code,
            {
              days: indexItem?.days ?? null,
              max: indexItem?.max_value ?? null,
              notAvailable: indexItem?.not_available ?? false
            }
          ];
        })
      ) as Record<string, IndexCell>;

      return {
        market: item.market,
        start: item.start,
        end: item.end,
        description: item.description,
        indices,
        turnoverDays: turnoverItem?.days ?? null,
        turnoverMax: turnoverItem?.max_value ?? null
      };
    });
  });

  const mergedColumns = computed(() => buildMergedColumns(t, indexConfigs));

  return {
    indexConfigs,
    filterForm,
    loading,
    loadStats,
    turnoverStats,
    mergedRows,
    mergedColumns,
    getIndexTotalDays
  };
}
