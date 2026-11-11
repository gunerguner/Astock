<template>
  <div class="page-container">
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
  import { computed, type Ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import type { TableColumnData, TableData } from '@arco-design/web-vue';
  import { fetchStockRanking, fetchTurnoverRanking } from '@/api/analysis';
  import AsyncState from '@/components/async-state/index.vue';
  import SyncMetaBadge from '@/components/sync-meta-badge/index.vue';
  import useAsyncRequest from '@/hooks/async-request';
  import usePageRefresh from '@/hooks/use-page-refresh';
  import { useIsMobile, mobileColumn } from '@/hooks/responsive';
  import useSyncStatus from '@/hooks/use-sync-status';
  import useTableScroll from '@/hooks/use-table-scroll';
  import { toTableRow } from '@/hooks/grouped-table';
  import { formatAmount } from '@/utils/format';
  import { renderNumCell } from '@/utils/table-cells';

  const { t } = useI18n();
  const isMobile = useIsMobile();
  const tableScroll = useTableScroll();

  defineOptions({
    name: 'TurnoverRank',
  });

  const DEFAULT_TOP = 20;

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

  const marketColumns = computed<TableColumnData[]>(() => [
    {
      title: t('pages.turnoverRank.columns.rank'),
      dataIndex: 'rank',
      width: 72,
      align: 'right',
      ...mobileColumn(isMobile.value, 72, 'left'),
    },
    {
      title: t('pages.turnoverRank.columns.date'),
      dataIndex: 'date',
      width: 118,
    },
    {
      title: t('pages.turnoverRank.columns.sh'),
      align: 'right',
      width: 110,
      render: ({ record }: { record: TableData }) => {
        const row = toTableRow<API.TurnoverRankingItem>(record);
        return renderNumCell(formatAmount(row.sse_amount));
      },
    },
    {
      title: t('pages.turnoverRank.columns.sz'),
      align: 'right',
      width: 110,
      render: ({ record }: { record: TableData }) => {
        const row = toTableRow<API.TurnoverRankingItem>(record);
        return renderNumCell(formatAmount(row.szse_amount));
      },
    },
    {
      title: t('pages.turnoverRank.columns.total'),
      align: 'right',
      width: 120,
      render: ({ record }: { record: TableData }) => {
        const row = toTableRow<API.TurnoverRankingItem>(record);
        return renderNumCell(formatAmount(row.turnover));
      },
    },
  ]);

  const stockColumns = computed<TableColumnData[]>(() => [
    {
      title: t('pages.turnoverRank.columns.rank'),
      dataIndex: 'rank',
      width: 72,
      align: 'right',
      ...mobileColumn(isMobile.value, 72, 'left'),
    },
    {
      title: t('pages.turnoverRank.columns.date'),
      dataIndex: 'date',
      width: 118,
    },
    {
      title: t('pages.turnoverRank.columns.stockName'),
      dataIndex: 'name',
      width: 120,
    },
    {
      title: t('pages.turnoverRank.columns.stockCode'),
      dataIndex: 'code',
      width: 96,
    },
    {
      title: t('pages.turnoverRank.columns.turnover'),
      align: 'right',
      width: 120,
      render: ({ record }: { record: TableData }) => {
        const row = toTableRow<API.StockRankingItem>(record);
        return renderNumCell(formatAmount(row.amount));
      },
    },
  ]);

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
      ...panels.value.map((panel) => panel.run()),
      loadSyncStatus(),
    ]);
  });
</script>
