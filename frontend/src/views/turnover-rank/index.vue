<template>
  <div class="page-container">
    <a-row :gutter="16">
      <a-col :span="12">
        <a-card title="大盘成交额排名" class="section-card">
          <template #extra>
            <span v-if="turnoverMetaText" class="meta-text">{{
              turnoverMetaText
            }}</span>
          </template>
          <a-table
            :columns="marketColumns"
            :data="marketRanking?.items ?? []"
            :loading="marketLoading"
            :pagination="false"
            row-key="rank"
          />
        </a-card>
      </a-col>
      <a-col :span="12">
        <a-card title="个股成交额排名" class="section-card">
          <template #extra>
            <span v-if="stockMetaText" class="meta-text">{{
              stockMetaText
            }}</span>
          </template>
          <a-table
            :columns="stockColumns"
            :data="stockRanking?.items ?? []"
            :loading="stockLoading"
            :pagination="false"
            row-key="rank"
          />
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script lang="ts" setup>
  import { computed, onMounted, ref } from 'vue';
  import type { TableColumnData } from '@arco-design/web-vue';
  import {
    fetchStockRanking,
    fetchTurnoverRanking,
    type StockRanking,
    type TurnoverRanking,
  } from '@/api/analysis';
  import { fetchSyncStatusApi, type SyncStatus } from '@/api/admin';
  import { formatAmount } from '@/utils/format';
  import formatSyncMeta from '@/utils/sync-meta';

  defineOptions({
    name: 'TurnoverRank',
  });

  const DEFAULT_TOP = 20;
  const marketLoading = ref(false);
  const stockLoading = ref(false);
  const marketRanking = ref<TurnoverRanking | null>(null);
  const stockRanking = ref<StockRanking | null>(null);
  const syncStatus = ref<SyncStatus | null>(null);

  const turnoverMetaText = computed(() =>
    formatSyncMeta(syncStatus.value?.turnover)
  );
  const stockMetaText = computed(() => formatSyncMeta(syncStatus.value?.stock));

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

  const loadMarketRanking = async () => {
    marketLoading.value = true;
    try {
      const res = await fetchTurnoverRanking(DEFAULT_TOP);
      marketRanking.value = res.data;
    } finally {
      marketLoading.value = false;
    }
  };

  const loadStockRanking = async () => {
    stockLoading.value = true;
    try {
      const res = await fetchStockRanking(DEFAULT_TOP);
      stockRanking.value = res.data;
    } finally {
      stockLoading.value = false;
    }
  };

  const loadSyncStatus = async () => {
    try {
      const res = await fetchSyncStatusApi();
      syncStatus.value = res.data;
    } catch {
      // 静默失败，不影响主要数据展示
    }
  };

  onMounted(() => {
    Promise.all([loadMarketRanking(), loadStockRanking(), loadSyncStatus()]);
  });
</script>
