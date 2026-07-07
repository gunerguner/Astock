<template>
  <div class="page-container">
    <a-card title="全球市场概览" class="section-card">
      <template #extra>
        <span v-if="metaText" class="meta-text">{{ metaText }}</span>
      </template>
      <a-table
        :columns="columns"
        :data="tableRows"
        :loading="loading"
        :pagination="false"
        :scroll="tableScrollX"
        :span-method="spanMethod"
        :row-class="rowClass"
        row-key="key"
      />
    </a-card>
  </div>
</template>

<script lang="ts" setup>
  import { computed, h, onMounted } from 'vue';
  import type { TableColumnData } from '@arco-design/web-vue';
  import { fetchMarketOverview, type MarketOverviewItem } from '@/api/analysis';
  import useAsyncRequest from '@/hooks/async-request';
  import {
    isDividerRow,
    toTableRow,
    useDividerTable,
    type BaseDividerRow,
  } from '@/hooks/grouped-table';
  import { formatPercent, formatPrice, getPercentColor } from '@/utils/format';
  import tableScrollX from '@/utils/table';

  defineOptions({
    name: 'MarketOverview',
  });

  interface DividerRow extends BaseDividerRow {
    periodText: string;
  }

  type TableRow = (MarketOverviewItem & { rowKind?: 'data' }) | DividerRow;

  const {
    loading,
    data: overview,
    run: loadOverview,
  } = useAsyncRequest((forceRefresh?: boolean) =>
    fetchMarketOverview(forceRefresh ?? false)
  );

  const metaText = computed(() => {
    if (!overview.value?.latest_trading_date) return '';
    return `最新数据日期 ${overview.value.latest_trading_date}`;
  });

  const formatPeriod = (start: string | null, end: string | null) => {
    if (!start || !end) return '';
    if (start === end) return start;
    return `${start} 至 ${end}`;
  };

  const tableRows = computed<TableRow[]>(() => {
    const categories = overview.value?.categories ?? [];
    const rows: TableRow[] = [];

    categories.forEach((cat) => {
      const validItems = cat.items.filter((item) => !item.error);
      const periodStarts = validItems
        .map((item) => item.period_start)
        .filter(Boolean) as string[];
      const periodEnds = validItems
        .map((item) => item.period_end)
        .filter(Boolean) as string[];
      const periodStart =
        periodStarts.length > 0
          ? periodStarts.reduce((a, b) => (a < b ? a : b))
          : null;
      const periodEnd =
        periodEnds.length > 0
          ? periodEnds.reduce((a, b) => (a > b ? a : b))
          : null;
      const periodText = formatPeriod(periodStart, periodEnd);

      rows.push({
        key: `divider-${cat.key}`,
        rowKind: 'divider',
        label: cat.name,
        periodText,
      });

      cat.items.forEach((item) => {
        rows.push({ ...item, rowKind: 'data' });
      });
    });

    return rows;
  });

  const columns: TableColumnData[] = [
    {
      title: '资产',
      render: ({ record }) => {
        const row = toTableRow<TableRow>(record);
        if (isDividerRow(row)) {
          const suffix = row.periodText ? `（${row.periodText}）` : '';
          return h(
            'span',
            { class: 'section-divider-label' },
            `${row.label}${suffix}`
          );
        }
        return h('span', [
          h('span', { class: 'asset-name-text' }, row.name),
          h('span', { class: 'asset-code-text' }, ` (${row.code})`),
        ]);
      },
    },
    {
      title: '最新价',
      render: ({ record }) => {
        const row = toTableRow<TableRow>(record);
        if (isDividerRow(row)) return null;
        if (row.error) return '数据获取失败';
        return formatPrice(row.current_price);
      },
    },
    {
      title: '日涨跌',
      render: ({ record }) => {
        const row = toTableRow<TableRow>(record);
        if (isDividerRow(row) || row.error) return null;
        return h(
          'span',
          { style: { color: getPercentColor(row.daily_change) } },
          formatPercent(row.daily_change)
        );
      },
    },
    {
      title: '周涨跌',
      render: ({ record }) => {
        const row = toTableRow<TableRow>(record);
        if (isDividerRow(row) || row.error) return null;
        return h(
          'span',
          { style: { color: getPercentColor(row.weekly_change) } },
          formatPercent(row.weekly_change)
        );
      },
    },
  ];

  const { spanMethod, rowClass } = useDividerTable(columns);

  onMounted(() => {
    loadOverview();
  });
</script>

<style scoped lang="less">
  .asset-name-text {
    font-weight: 500;
  }

  .asset-code-text {
    color: var(--color-text-3);
    font-size: 12px;
  }
</style>
