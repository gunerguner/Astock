<template>
  <div class="container">
    <a-row :gutter="16">
      <a-col :span="12">
        <a-card title="大盘成交额排名" class="section-card">
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
  import { onMounted, ref } from 'vue';
  import type { TableColumnData } from '@arco-design/web-vue';
  import {
    fetchStockRanking,
    fetchTurnoverRanking,
    type StockRanking,
    type TurnoverRanking,
  } from '@/api/analysis';
  import { formatAmount } from '@/utils/format';

  const DEFAULT_TOP = 20;
  const marketLoading = ref(false);
  const stockLoading = ref(false);
  const marketRanking = ref<TurnoverRanking | null>(null);
  const stockRanking = ref<StockRanking | null>(null);

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

  onMounted(() => {
    Promise.all([loadMarketRanking(), loadStockRanking()]);
  });
</script>

<script lang="ts">
  export default {
    name: 'TurnoverRank',
  };
</script>

<style scoped lang="less">
  .container {
    padding: 16px 20px 20px;
  }

  .section-card {
    height: 100%;
  }
</style>
