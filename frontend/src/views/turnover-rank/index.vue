<template>
  <div class="page-container">
    <a-row :gutter="[16, 16]">
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
            :scroll="tableScrollX"
            row-key="rank"
          />
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script lang="ts" setup>
  import { onMounted, ref, type Ref } from 'vue';
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
  import tableScrollX from '@/utils/table';
  import formatSyncMeta from '@/utils/sync-meta';

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

  const marketColumns: TableColumnData[] = [
    { title: '排名', dataIndex: 'rank', width: 80 },
    { title: '日期', dataIndex: 'date' },
    {
      title: '上证',
      render: ({ record }) => formatAmount(record.sh_amount),
    },
    {
      title: '深证',
      render: ({ record }) => formatAmount(record.sz_amount),
    },
    {
      title: '合计成交额',
      render: ({ record }) => formatAmount(record.turnover),
    },
  ];

  const stockColumns: TableColumnData[] = [
    { title: '排名', dataIndex: 'rank', width: 80 },
    { title: '日期', dataIndex: 'date' },
    { title: '股票代码', dataIndex: 'code' },
    { title: '股票名称', dataIndex: 'name' },
    {
      title: '成交额',
      render: ({ record }) => formatAmount(record.amount),
    },
  ];

  const marketPanel = useAsyncRequest(() => fetchTurnoverRanking(DEFAULT_TOP));
  const stockPanel = useAsyncRequest(() => fetchStockRanking(DEFAULT_TOP));

  const panels: RankingPanel[] = [
    {
      key: 'market',
      title: '大盘成交额排名',
      columns: marketColumns,
      syncKey: 'turnover',
      request: () => fetchTurnoverRanking(DEFAULT_TOP),
      ...marketPanel,
    },
    {
      key: 'stock',
      title: '个股成交额排名',
      columns: stockColumns,
      syncKey: 'stock',
      request: () => fetchStockRanking(DEFAULT_TOP),
      ...stockPanel,
    },
  ];

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

  onMounted(() => {
    Promise.all([...panels.map((panel) => panel.run()), loadSyncStatus()]);
  });
</script>
