<template>
  <div class="page-container">
    <a-card :title="$t('pages.bullMarket.title')" class="section-card">
      <template #extra>
        <span v-if="metaText" class="meta-text">{{ metaText }}</span>
        <span
          v-for="index in indexConfigs"
          :key="index.code"
          class="total-summary"
        >
          {{
            $t('pages.bullMarket.indexStandardDays', {
              name: $t(index.nameKey),
            })
          }}
          <strong>{{ getIndexTotalDays(index.code) }}</strong>
          {{ $t('pages.bullMarket.unitDays') }}
        </span>
        <span class="total-summary">
          {{ $t('pages.bullMarket.turnoverStandardDays') }}
          <strong>{{ turnoverStats?.total_days ?? '-' }}</strong>
          {{ $t('pages.bullMarket.unitDays') }}
        </span>
      </template>
      <a-form
        :model="filterForm"
        class="filter-form"
        layout="inline"
        @submit-success="loadStats"
      >
        <a-form-item
          v-for="index in indexConfigs"
          :key="index.code"
          :label="$t(index.filterKey)"
          :field="`pointThresholds.${index.code}`"
        >
          <a-input-number
            v-model="filterForm.pointThresholds[index.code]"
            :min="1"
            :step="100"
            :precision="0"
            :style="{ width: '120px' }"
          />
        </a-form-item>
        <a-form-item
          :label="$t('pages.bullMarket.turnoverLabelShort')"
          field="turnoverThresholdTrillion"
        >
          <a-input-number
            v-model="filterForm.turnoverThresholdTrillion"
            :min="0.01"
            :step="0.1"
            :precision="2"
            :style="{ width: '140px' }"
          />
        </a-form-item>
        <a-form-item class="filter-submit">
          <a-button type="primary" html-type="submit" :loading="loading">
            {{ $t('pages.bullMarket.query') }}
          </a-button>
        </a-form-item>
      </a-form>
      <div class="table-wrap">
        <a-table
          class="result-table"
          :columns="mergedColumns"
          :data="mergedRows"
          :loading="loading"
          :pagination="false"
          :scroll="tableScroll"
          row-key="market"
        />
      </div>
    </a-card>
  </div>
</template>

<script lang="ts" setup>
  import { computed, h, onMounted, onUnmounted, reactive, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { Tooltip } from '@arco-design/web-vue';
  import type { TableColumnData } from '@arco-design/web-vue';
  import {
    DEFAULT_POINT_THRESHOLDS,
    fetchBullMarketPointStats,
    fetchBullMarketTurnoverStats,
    POINT_INDEX_CODES,
    type BullMarketStats,
    type MultiIndexPointStats,
  } from '@/api/analysis';
  import { fetchSyncStatusApi, type SyncStatus } from '@/api/admin';
  import useAsyncRequest from '@/hooks/async-request';
  import { formatAmount, formatPoint, numClass } from '@/utils/format';
  import useTableScroll from '@/utils/table';
  import formatSyncMeta from '@/utils/sync-meta';
  import { offDataRefresh, onDataRefresh } from '@/utils/data-refresh';

  const { t } = useI18n();
  const tableScroll = useTableScroll();

  defineOptions({
    name: 'BullMarket',
  });

  const indexConfigs = [
    {
      code: '000001',
      nameKey: 'pages.bullMarket.indexSh',
      filterKey: 'pages.bullMarket.filterSh',
    },
    {
      code: '000300',
      nameKey: 'pages.bullMarket.indexHS300',
      filterKey: 'pages.bullMarket.filterHS300',
    },
    {
      code: '399006',
      nameKey: 'pages.bullMarket.indexCYB',
      filterKey: 'pages.bullMarket.filterCYB',
    },
    {
      code: '000688',
      nameKey: 'pages.bullMarket.indexKCB50',
      filterKey: 'pages.bullMarket.filterKCB50',
    },
  ] as const;

  const formatPeriodCompact = (start: string, end: string) => `${start}~${end}`;

  interface IndexCell {
    days: number | null;
    max: number | null;
    notAvailable: boolean;
  }

  interface MergedRow {
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

  const filterForm = reactive({
    pointThresholds: { ...DEFAULT_POINT_THRESHOLDS },
    turnoverThresholdTrillion: 2,
  });

  const {
    loading,
    data: statsData,
    run: loadStats,
  } = useAsyncRequest(async (): Promise<BullStatsPair> => {
    const [point, turnover] = await Promise.all([
      fetchBullMarketPointStats(filterForm.pointThresholds),
      fetchBullMarketTurnoverStats(filterForm.turnoverThresholdTrillion * 1e12),
    ]);
    return { point, turnover };
  });

  const pointStats = computed(() => statsData.value?.point ?? null);
  const turnoverStats = computed(() => statsData.value?.turnover ?? null);
  const syncStatus = ref<SyncStatus | null>(null);

  const metaText = computed(() =>
    formatSyncMeta(syncStatus.value?.point, syncStatus.value?.turnover)
  );

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

  const formatDays = (
    value: number | null | undefined,
    notAvailable = false
  ) => {
    if (notAvailable) {
      return '—';
    }
    if (value === null || value === undefined) {
      return '-';
    }
    return String(value);
  };

  const renderUnavailableCell = (content: string, notAvailable: boolean) => {
    if (!notAvailable) {
      return h('span', { class: 'num' }, content);
    }
    return h(
      Tooltip,
      { content: t('pages.bullMarket.notAvailable') },
      {
        default: () => h('span', { class: 'num unavailable' }, content),
      }
    );
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
              notAvailable: indexItem?.not_available ?? false,
            },
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
        turnoverMax: turnoverItem?.max_value ?? null,
      };
    });
  });

  const mergedColumns = computed<TableColumnData[]>(() => {
    const indexColumns: TableColumnData[] = indexConfigs.map((index) => ({
      title: t(index.filterKey),
      children: [
        {
          title: t('pages.bullMarket.columns.standardDaysShort'),
          align: 'right',
          width: 56,
          render: ({ record }) => {
            const row = record as MergedRow;
            const cell = row.indices[index.code];
            return renderUnavailableCell(
              formatDays(cell?.days, cell?.notAvailable),
              cell?.notAvailable ?? false
            );
          },
        },
        {
          title: t('pages.bullMarket.columns.maxPointShort'),
          align: 'right',
          width: 76,
          render: ({ record }) => {
            const row = record as MergedRow;
            const cell = row.indices[index.code];
            const content = cell?.notAvailable
              ? '—'
              : formatPoint(cell?.max ?? null);
            if (cell?.notAvailable) {
              return renderUnavailableCell(content, true);
            }
            return h('span', { class: numClass(cell?.max ?? null) }, content);
          },
        },
      ],
    }));

    return [
      {
        title: t('pages.bullMarket.columns.market'),
        dataIndex: 'market',
        width: 88,
      },
      {
        title: t('pages.bullMarket.columns.period'),
        width: 168,
        render: ({ record }) => formatPeriodCompact(record.start, record.end),
      },
      ...indexColumns,
      {
        title: t('pages.bullMarket.columns.turnoverDimensionShort'),
        children: [
          {
            title: t('pages.bullMarket.columns.standardDaysShort'),
            align: 'right',
            width: 56,
            render: ({ record }) =>
              h('span', { class: 'num' }, formatDays(record.turnoverDays)),
          },
          {
            title: t('pages.bullMarket.columns.maxTurnoverShort'),
            align: 'right',
            width: 88,
            render: ({ record }) =>
              h('span', { class: 'num' }, formatAmount(record.turnoverMax)),
          },
        ],
      },
    ];
  });

  const loadSyncStatus = async () => {
    try {
      syncStatus.value = await fetchSyncStatusApi();
    } catch {
      // 静默失败，不影响主要数据展示
    }
  };

  const reloadPageData = () => {
    loadStats();
    loadSyncStatus();
  };

  onMounted(() => {
    onDataRefresh(reloadPageData);
    reloadPageData();
  });

  onUnmounted(() => {
    offDataRefresh(reloadPageData);
  });
</script>

<style scoped lang="less">
  .section-card {
    height: auto;
    margin-bottom: 16px;
  }

  .total-summary {
    display: inline-flex;
    align-items: center;
    color: var(--color-text-2);
    font-size: var(--fs-body);
    line-height: var(--lh-title);
    margin-left: 0;

    strong {
      color: var(--brand-6);
      font-size: var(--fs-title);
      font-variant-numeric: tabular-nums;
      font-feature-settings: 'tnum';
    }
  }

  .table-wrap {
    margin-top: 8px;
  }

  .result-table {
    :deep(.arco-table-th),
    :deep(.arco-table-td) {
      padding-left: 8px;
      padding-right: 8px;
    }

    :deep(.arco-table-cell) {
      padding: 8px 4px;
      font-size: 13px;
    }
  }

  .filter-form {
    display: flex;
    flex-wrap: nowrap;
    align-items: center;
    gap: 0;
    margin-bottom: 24px;

    :deep(.arco-form-item) {
      margin-bottom: 0;
      margin-right: 12px;
      flex-shrink: 0;
    }

    :deep(.arco-form-item-label) {
      padding-right: 6px;
      font-size: 13px;
      white-space: nowrap;
    }

    :deep(.arco-form-item-label-col) {
      flex: none;
    }

    .filter-submit {
      margin-right: 0;
    }
  }

  :deep(.unavailable) {
    color: var(--color-text-3);
    cursor: help;
  }
</style>
