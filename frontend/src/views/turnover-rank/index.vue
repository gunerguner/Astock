<template>
  <div class="page-container">
    <a-row :gutter="[20, 20]">
      <a-col v-for="panel in panels" :key="panel.key" :xs="24" :md="12">
        <a-card :title="panel.title" class="section-card">
          <template #extra>
            <span v-if="panelMetaText(panel.syncKey)" class="meta-text">
              {{ panelMetaText(panel.syncKey) }}
            </span>
          </template>
          <a-table
            :columns="panel.columns"
            :data="getPanelItems(panel)"
            :loading="isPanelLoading(panel)"
            :pagination="false"
            :scroll="tableScroll"
            row-key="rank"
          />
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script lang="ts" setup>
  import { computed, h, onMounted, onUnmounted, ref, type Ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import type { TableColumnData } from '@arco-design/web-vue';
  import {
    fetchStockRanking,
    fetchTurnoverRanking,
    type StockRanking,
    type TurnoverRanking,
  } from '@/api/analysis';
  import { fetchSyncStatusApi, type SyncStatus } from '@/api/admin';
  import useAsyncRequest from '@/hooks/async-request';
  import { formatAmount } from '@/utils/format';
  import useTableScroll from '@/utils/table';
  import formatSyncMeta from '@/utils/sync-meta';
  import { offDataRefresh, onDataRefresh } from '@/utils/data-refresh';

  const { t } = useI18n();
  const tableScroll = useTableScroll();

  defineOptions({
    name: 'TurnoverRank',
  });

  const DEFAULT_TOP = 20;

  type PanelSyncKey = 'turnover' | 'stock';

  type RankingResult = TurnoverRanking | StockRanking;

  interface RankingPanel {
    key: string;
    title: string;
    columns: TableColumnData[];
    syncKey: PanelSyncKey;
    request: () => Promise<RankingResult>;
    loading: Ref<boolean>;
    data: Ref<RankingResult | null>;
    run: () => Promise<RankingResult>;
  }

  const marketColumns = computed<TableColumnData[]>(() => [
    {
      title: t('pages.turnoverRank.columns.rank'),
      dataIndex: 'rank',
      width: 72,
      align: 'right',
    },
    { title: t('pages.turnoverRank.columns.date'), dataIndex: 'date' },
    {
      title: t('pages.turnoverRank.columns.sh'),
      align: 'right',
      render: ({ record }) =>
        h('span', { class: 'num' }, formatAmount(record.sh_amount)),
    },
    {
      title: t('pages.turnoverRank.columns.sz'),
      align: 'right',
      render: ({ record }) =>
        h('span', { class: 'num' }, formatAmount(record.sz_amount)),
    },
    {
      title: t('pages.turnoverRank.columns.total'),
      align: 'right',
      render: ({ record }) =>
        h('span', { class: 'num' }, formatAmount(record.turnover)),
    },
  ]);

  const stockColumns = computed<TableColumnData[]>(() => [
    {
      title: t('pages.turnoverRank.columns.rank'),
      dataIndex: 'rank',
      width: 72,
      align: 'right',
    },
    { title: t('pages.turnoverRank.columns.date'), dataIndex: 'date' },
    {
      title: t('pages.turnoverRank.columns.stockName'),
      dataIndex: 'name',
    },
    {
      title: t('pages.turnoverRank.columns.stockCode'),
      dataIndex: 'code',
      width: 96,
    },
    {
      title: t('pages.turnoverRank.columns.turnover'),
      align: 'right',
      render: ({ record }) =>
        h('span', { class: 'num' }, formatAmount(record.amount)),
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
      request: () => fetchTurnoverRanking(DEFAULT_TOP),
      ...marketPanel,
    },
    {
      key: 'stock',
      title: t('pages.turnoverRank.stockTitle'),
      columns: stockColumns.value,
      syncKey: 'stock',
      request: () => fetchStockRanking(DEFAULT_TOP),
      ...stockPanel,
    },
  ]);

  const syncStatus = ref<SyncStatus | null>(null);

  const panelMetaText = (syncKey: PanelSyncKey) =>
    formatSyncMeta(syncStatus.value?.[syncKey]);

  const getPanelItems = (panel: RankingPanel) => panel.data.value?.items ?? [];

  const isPanelLoading = (panel: RankingPanel) => panel.loading.value;

  const loadSyncStatus = async () => {
    try {
      syncStatus.value = await fetchSyncStatusApi();
    } catch {
      // 静默失败，不影响主要数据展示
    }
  };

  const reloadPageData = () => {
    Promise.all([
      ...panels.value.map((panel) => panel.run()),
      loadSyncStatus(),
    ]);
  };

  onMounted(() => {
    onDataRefresh(reloadPageData);
    reloadPageData();
  });

  onUnmounted(() => {
    offDataRefresh(reloadPageData);
  });
</script>
