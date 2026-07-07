<template>
  <div class="page-container">
    <a-card :title="$t('pages.bullMarket.title')" class="section-card">
      <template #extra>
        <span v-if="metaText" class="meta-text">{{ metaText }}</span>
        <span class="total-summary">
          {{ $t('pages.bullMarket.pointStandardDays') }}
          <strong>{{ pointStats?.total_days ?? '-' }}</strong>
          {{ $t('pages.bullMarket.unitDays') }}
        </span>
        <span class="total-summary">
          {{ $t('pages.bullMarket.turnoverStandardDays') }}
          <strong>{{ turnoverStats?.total_days ?? '-' }}</strong>
          {{ $t('pages.bullMarket.unitDays') }}
        </span>
      </template>
      <a-form :model="filterForm" layout="inline" @submit-success="loadStats">
        <a-form-item
          :label="$t('pages.bullMarket.pointLabel')"
          field="pointThreshold"
        >
          <a-input-number
            v-model="filterForm.pointThreshold"
            :min="1"
            :step="100"
            :precision="0"
            style="width: 200px"
          />
        </a-form-item>
        <a-form-item
          :label="$t('pages.bullMarket.turnoverLabel')"
          field="turnoverThresholdTrillion"
        >
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
            {{ $t('pages.bullMarket.query') }}
          </a-button>
        </a-form-item>
      </a-form>
      <a-table
        class="result-table"
        :columns="mergedColumns"
        :data="mergedRows"
        :loading="loading"
        :pagination="false"
        :scroll="tableScroll"
        row-key="market"
      />
    </a-card>
  </div>
</template>

<script lang="ts" setup>
  import { computed, h, onMounted, reactive, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import type { TableColumnData } from '@arco-design/web-vue';
  import {
    fetchBullMarketPointStats,
    fetchBullMarketTurnoverStats,
    type BullMarketStats,
  } from '@/api/analysis';
  import { fetchSyncStatusApi, type SyncStatus } from '@/api/admin';
  import useAsyncRequest from '@/hooks/async-request';
  import {
    formatAmount,
    formatPeriod,
    formatPoint,
    numClass,
  } from '@/utils/format';
  import useTableScroll from '@/utils/table';
  import formatSyncMeta from '@/utils/sync-meta';

  const { t } = useI18n();
  const tableScroll = useTableScroll();

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

  const mergedColumns = computed<TableColumnData[]>(() => [
    {
      title: t('pages.bullMarket.columns.market'),
      dataIndex: 'market',
      width: 140,
    },
    {
      title: t('pages.bullMarket.columns.period'),
      render: ({ record }) => formatPeriod(record.start, record.end),
    },
    {
      title: t('pages.bullMarket.columns.pointDimension'),
      children: [
        {
          title: t('pages.bullMarket.columns.standardDays'),
          align: 'right',
          render: ({ record }) =>
            h('span', { class: 'num' }, formatDays(record.pointDays)),
        },
        {
          title: t('pages.bullMarket.columns.maxPoint'),
          align: 'right',
          render: ({ record }) =>
            h(
              'span',
              { class: numClass(record.pointMax) },
              formatPoint(record.pointMax)
            ),
        },
      ],
    },
    {
      title: t('pages.bullMarket.columns.turnoverDimension'),
      children: [
        {
          title: t('pages.bullMarket.columns.standardDays'),
          align: 'right',
          render: ({ record }) =>
            h('span', { class: 'num' }, formatDays(record.turnoverDays)),
        },
        {
          title: t('pages.bullMarket.columns.maxTurnover'),
          align: 'right',
          render: ({ record }) =>
            h('span', { class: 'num' }, formatAmount(record.turnoverMax)),
        },
      ],
    },
  ]);

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

  .result-table {
    margin-top: 16px;
  }
</style>
