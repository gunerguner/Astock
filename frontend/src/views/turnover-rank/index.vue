<template>
  <div class="page-container">
    <a-card class="section-card turnover-chart-card">
      <template #title>
        <div class="chart-heading">
          <span>{{ t('pages.turnoverRank.chart.title') }}</span>
          <div class="range-segment" role="tablist">
            <button
              v-for="item in rangeOptions"
              :key="item.value"
              type="button"
              class="range-segment-item"
              role="tab"
              :class="{ 'is-active': seriesRange === item.value }"
              :aria-selected="seriesRange === item.value"
              @click="onRangeChange(item.value)"
            >
              {{ t(item.label) }}
            </button>
          </div>
        </div>
      </template>
      <template #extra>
        <SyncMetaBadge
          :failed="syncFailed"
          :text="panelMetaText('turnover')"
          @retry="loadSyncStatus"
        />
      </template>
      <AsyncState
        :loading="seriesLoading"
        :error="seriesError"
        :has-data="chartHasData"
        :empty-text="t('pages.turnoverRank.chart.noData')"
        :min-height="'var(--chart-height-main)'"
        @retry="loadSeries()"
      >
        <div ref="chartRef" class="chart-canvas" />
      </AsyncState>
    </a-card>

    <a-row :gutter="[20, 20]">
      <a-col v-for="panel in panels" :key="panel.key" :xs="24" :md="12">
        <a-card :title="panel.title" class="section-card section-card--fill">
          <template #extra>
            <SyncMetaBadge
              :failed="syncFailed"
              :text="panelMetaText(panel.syncKey)"
              @retry="loadSyncStatus"
            />
          </template>
          <AsyncState
            :loading="panel.loading.value"
            :error="panel.error.value"
            :has-data="panel.data.value !== null"
            @retry="panel.run()"
          >
            <a-table
              :columns="panel.columns"
              :data="getPanelItems(panel)"
              :loading="panel.loading.value && panel.data.value !== null"
              :pagination="false"
              :scroll="tableScroll"
              row-key="rank"
            />
          </AsyncState>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script lang="ts" setup>
  import { computed, ref, type Ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import type { TableColumnData } from '@arco-design/web-vue';
  import {
    fetchStockRanking,
    fetchTurnoverRanking,
    fetchTurnoverSeries,
  } from '@/api/analysis';
  import AsyncState from '@/components/async-state/index.vue';
  import SyncMetaBadge from '@/components/sync-meta-badge/index.vue';
  import useAsyncRequest from '@/hooks/async-request';
  import usePageRefresh from '@/hooks/use-page-refresh';
  import { useIsMobile } from '@/hooks/responsive';
  import useSyncStatus from '@/hooks/use-sync-status';
  import useTableScroll from '@/hooks/use-table-scroll';
  import { buildMarketColumns, buildStockColumns } from './columns';
  import useTurnoverChart from './use-turnover-chart';

  const { t } = useI18n();
  const isMobile = useIsMobile();
  const tableScroll = useTableScroll();

  defineOptions({
    name: 'TurnoverRank',
  });

  const DEFAULT_TOP = 20;

  const chartRef = ref<HTMLElement | null>(null);
  const seriesRange = ref<API.TurnoverRange>('1y');
  const rangeOptions: Array<{ value: API.TurnoverRange; label: string }> = [
    { value: '1y', label: 'pages.turnoverRank.chart.range1y' },
    { value: '5y', label: 'pages.turnoverRank.chart.range5y' },
    { value: 'all', label: 'pages.turnoverRank.chart.rangeAll' },
  ];

  const {
    loading: seriesLoading,
    data: series,
    error: seriesError,
    run: loadSeries,
  } = useAsyncRequest(() => fetchTurnoverSeries(seriesRange.value));

  const seriesPoints = computed<API.TurnoverSeriesItem[]>(
    () => series.value?.items ?? [],
  );
  const { hasData: chartHasData } = useTurnoverChart(chartRef, seriesPoints);

  function onRangeChange(value: API.TurnoverRange) {
    if (value === seriesRange.value) return;
    seriesRange.value = value;
    loadSeries();
  }

  type PanelSyncKey = 'turnover' | 'stock';
  type RankingResult = API.TurnoverRanking | API.StockRanking;

  interface RankingPanel {
    key: string;
    title: string;
    columns: TableColumnData[];
    syncKey: PanelSyncKey;
    loading: Ref<boolean>;
    data: Ref<RankingResult | null>;
    error: Ref<unknown>;
    run: () => Promise<RankingResult | undefined>;
  }

  const marketColumns = computed(() => buildMarketColumns(t, isMobile.value));
  const stockColumns = computed(() => buildStockColumns(t, isMobile.value));

  const marketPanel = useAsyncRequest(() => fetchTurnoverRanking(DEFAULT_TOP));
  const stockPanel = useAsyncRequest(() => fetchStockRanking(DEFAULT_TOP));

  const panels = computed<RankingPanel[]>(() => [
    {
      key: 'market',
      title: t('pages.turnoverRank.marketTitle'),
      columns: marketColumns.value,
      syncKey: 'turnover',
      ...marketPanel,
    },
    {
      key: 'stock',
      title: t('pages.turnoverRank.stockTitle'),
      columns: stockColumns.value,
      syncKey: 'stock',
      ...stockPanel,
    },
  ]);

  const {
    panelMetaText,
    loadFailed: syncFailed,
    loadSyncStatus,
  } = useSyncStatus();

  const getPanelItems = (panel: RankingPanel) => panel.data.value?.items ?? [];

  usePageRefresh(() => {
    Promise.all([
      loadSeries(),
      ...panels.value.map((panel) => panel.run()),
      loadSyncStatus(),
    ]);
  });
</script>

<style scoped lang="less">
  .page-container {
    --chart-height-main: 360px;
  }

  .turnover-chart-card {
    margin-bottom: 20px;
  }

  .chart-heading {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px 16px;
  }

  .range-segment {
    display: inline-flex;
    align-items: center;
    gap: 2px;
  }

  .range-segment-item {
    height: 26px;
    margin: 0;
    padding: 0 10px;
    border: 0;
    border-radius: 4px;
    background: transparent;
    color: var(--color-text-2);
    font-family: inherit;
    font-size: var(--fs-body);
    font-weight: 400;
    line-height: 26px;
    cursor: pointer;

    &:hover {
      color: var(--brand-6);
    }

    &.is-active {
      background: var(--brand-1);
      color: var(--brand-6);
      font-weight: 600;
    }
  }

  .chart-canvas {
    width: 100%;
    height: var(--chart-height-main);
  }

  @media (max-width: @screen-mobile-max) {
    .page-container {
      --chart-height-main: 300px;
    }
  }
</style>
