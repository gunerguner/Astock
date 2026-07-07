<template>
  <div class="page-container">
    <a-card title="A股牛市数据总览" class="section-card">
      <template #extra>
        <span v-if="metaText" class="meta-text">{{ metaText }}</span>
        <span class="total-summary">
          点位达标：<strong>{{ pointStats?.total_days ?? '-' }}</strong> 天
        </span>
        <span class="total-summary">
          成交额达标：<strong>{{ turnoverStats?.total_days ?? '-' }}</strong> 天
        </span>
      </template>
      <a-form :model="filterForm" layout="inline" @submit-success="loadStats">
        <a-form-item label="点位阈值" field="pointThreshold">
          <a-input-number
            v-model="filterForm.pointThreshold"
            :min="1"
            :step="100"
            :precision="0"
            style="width: 200px"
          />
        </a-form-item>
        <a-form-item label="成交额阈值(万亿)" field="turnoverThresholdTrillion">
          <a-input-number
            v-model="filterForm.turnoverThresholdTrillion"
            :min="0.01"
            :step="0.1"
            :precision="2"
            style="width: 200px"
          />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" html-type="submit" :loading="loading">
            查询
          </a-button>
        </a-form-item>
      </a-form>
      <a-table
        class="result-table"
        :columns="mergedColumns"
        :data="mergedRows"
        :loading="loading"
        :pagination="false"
        :scroll="tableScrollX"
        row-key="market"
      />
    </a-card>
  </div>
</template>

<script lang="ts" setup>
  import { computed, onMounted, reactive, ref } from 'vue';
  import type { TableColumnData } from '@arco-design/web-vue';
  import {
    fetchBullMarketPointStats,
    fetchBullMarketTurnoverStats,
    type BullMarketStats,
  } from '@/api/analysis';
  import { fetchSyncStatusApi, type SyncStatus } from '@/api/admin';
  import useAsyncRequest from '@/hooks/async-request';
  import { formatAmount, formatPeriod, formatPoint } from '@/utils/format';
  import tableScrollX from '@/utils/table';
  import formatSyncMeta from '@/utils/sync-meta';

  defineOptions({
    name: 'BullMarket',
  });

  interface MergedRow {
    market: string;
    start: string;
    end: string;
    description?: string | null;
    pointDays: number | null;
    pointMax: number | null;
    turnoverDays: number | null;
    turnoverMax: number | null;
  }

  interface BullStatsPair {
    point: BullMarketStats;
    turnover: BullMarketStats;
  }

  const filterForm = reactive({
    pointThreshold: 4000,
    turnoverThresholdTrillion: 2,
  });
  const {
    loading,
    data: statsData,
    run: loadStats,
  } = useAsyncRequest(async (): Promise<BullStatsPair> => {
    const [point, turnover] = await Promise.all([
      fetchBullMarketPointStats(filterForm.pointThreshold),
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

  const formatDays = (value: number | null | undefined) => {
    if (value === null || value === undefined) {
      return '-';
    }
    return String(value);
  };

  const mergedRows = computed<MergedRow[]>(() => {
    const base = pointStats.value?.items ?? turnoverStats.value?.items ?? [];
    const turnoverByMarket = new Map(
      (turnoverStats.value?.items ?? []).map((item) => [item.market, item])
    );

    return base.map((item) => {
      const turnoverItem = turnoverByMarket.get(item.market);
      return {
        market: item.market,
        start: item.start,
        end: item.end,
        description: item.description,
        pointDays: pointStats.value ? item.days : null,
        pointMax: pointStats.value ? item.max_value : null,
        turnoverDays: turnoverItem?.days ?? null,
        turnoverMax: turnoverItem?.max_value ?? null,
      };
    });
  });

  const mergedColumns: TableColumnData[] = [
    { title: '牛市名称', dataIndex: 'market', width: 140 },
    {
      title: '区间',
      render: ({ record }) => formatPeriod(record.start, record.end),
    },
    {
      title: '点位维度',
      children: [
        {
          title: '达标天数',
          render: ({ record }) => formatDays(record.pointDays),
        },
        {
          title: '最高点位',
          render: ({ record }) => formatPoint(record.pointMax),
        },
      ],
    },
    {
      title: '成交额维度',
      children: [
        {
          title: '达标天数',
          render: ({ record }) => formatDays(record.turnoverDays),
        },
        {
          title: '最高成交额',
          render: ({ record }) => formatAmount(record.turnoverMax),
        },
      ],
    },
  ];

  const loadSyncStatus = async () => {
    try {
      syncStatus.value = await fetchSyncStatusApi();
    } catch {
      // 静默失败，不影响主要数据展示
    }
  };

  onMounted(() => {
    loadStats();
    loadSyncStatus();
  });
</script>

<style scoped lang="less">
  .section-card {
    height: auto;
    margin-bottom: 16px;
  }

  .meta-text {
    margin-right: 16px;
  }

  .total-summary {
    color: var(--color-text-2);
    font-size: 14px;
    margin-left: 16px;

    &:first-child {
      margin-left: 0;
    }

    strong {
      color: rgb(var(--primary-6));
      font-size: 18px;
    }
  }

  .result-table {
    margin-top: 16px;
  }
</style>
