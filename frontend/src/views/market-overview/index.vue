<template>
  <div class="container">
    <a-card title="全球市场概览" class="section-card">
      <template #extra>
        <span v-if="metaText" class="meta-text">{{ metaText }}</span>
      </template>
      <a-table
        :columns="columns"
        :data="tableRows"
        :loading="loading"
        :pagination="false"
        :span-method="spanMethod"
        :row-class="rowClass"
        row-key="key"
      />
    </a-card>
  </div>
</template>

<script lang="ts" setup>
  import { computed, h, onMounted, ref } from 'vue';
  import type { TableColumnData, TableData } from '@arco-design/web-vue';
  import {
    fetchMarketOverview,
    type MarketOverview,
    type MarketOverviewItem,
  } from '@/api/analysis';

  interface DividerRow {
    key: string;
    rowKind: 'divider';
    label: string;
    periodText: string;
  }

  type TableRow = (MarketOverviewItem & { rowKind?: 'data' }) | DividerRow;

  const loading = ref(false);
  const overview = ref<MarketOverview | null>(null);

  const metaText = computed(() => {
    if (!overview.value?.latest_trading_date) return '';
    return `最新数据日期 ${overview.value.latest_trading_date}`;
  });

  const formatPrice = (value: number | null) => {
    if (value === null || value === undefined) return '--';
    return value.toFixed(2);
  };

  const formatPct = (value: number | null) => {
    if (value === null || value === undefined) return '--';
    const prefix = value > 0 ? '+' : '';
    return `${prefix}${value.toFixed(2)}%`;
  };

  const pctColor = (value: number | null) => {
    if (value === null || value === undefined) return undefined;
    if (value > 0) return '#00b42a';
    if (value < 0) return '#f53f3f';
    return undefined;
  };

  const formatPeriod = (start: string | null, end: string | null) => {
    if (!start || !end) return '';
    if (start === end) return start;
    return `${start} 至 ${end}`;
  };

  const isDividerRow = (record: TableRow): record is DividerRow =>
    'rowKind' in record && record.rowKind === 'divider';

  const toTableRow = (record: TableData): TableRow => record as TableRow;

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

  const spanMethod = ({
    record,
    columnIndex,
  }: {
    record: TableData;
    columnIndex: number;
  }) => {
    const row = toTableRow(record);
    if (isDividerRow(row)) {
      if (columnIndex === 0) {
        return { rowspan: 1, colspan: columns.length };
      }
      return { rowspan: 0, colspan: 0 };
    }
    return { rowspan: 1, colspan: 1 };
  };

  const rowClass = (record: TableData) =>
    isDividerRow(toTableRow(record)) ? 'section-divider-row' : '';

  const columns: TableColumnData[] = [
    {
      title: '资产',
      render: ({ record }) => {
        const row = toTableRow(record);
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
        const row = toTableRow(record);
        if (isDividerRow(row)) return null;
        if (row.error) return '数据获取失败';
        return formatPrice(row.current_price);
      },
    },
    {
      title: '日涨跌',
      render: ({ record }) => {
        const row = toTableRow(record);
        if (isDividerRow(row) || row.error) return null;
        return h(
          'span',
          { style: { color: pctColor(row.daily_change) } },
          formatPct(row.daily_change)
        );
      },
    },
    {
      title: '周涨跌',
      render: ({ record }) => {
        const row = toTableRow(record);
        if (isDividerRow(row) || row.error) return null;
        return h(
          'span',
          { style: { color: pctColor(row.weekly_change) } },
          formatPct(row.weekly_change)
        );
      },
    },
  ];

  const loadOverview = async (forceRefresh = false) => {
    loading.value = true;
    try {
      const res = await fetchMarketOverview(forceRefresh);
      overview.value = res.data;
    } finally {
      loading.value = false;
    }
  };

  onMounted(() => {
    loadOverview();
  });
</script>

<script lang="ts">
  export default {
    name: 'MarketOverview',
  };
</script>

<style scoped lang="less">
  .container {
    padding: 16px 20px 20px;
  }

  .section-card {
    height: 100%;
  }

  .meta-text {
    color: var(--color-text-3);
    font-size: 13px;
  }

  .asset-name-text {
    font-weight: 500;
  }

  .asset-code-text {
    color: var(--color-text-3);
    font-size: 12px;
  }

  :deep(.section-divider-row) {
    td {
      background: var(--color-fill-2);
      border-top: 1px solid var(--color-border-2);
      border-bottom: 1px solid var(--color-border-2);
      padding-top: 10px;
      padding-bottom: 10px;
    }
  }

  .section-divider-label {
    color: var(--color-text-2);
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.02em;
  }
</style>
