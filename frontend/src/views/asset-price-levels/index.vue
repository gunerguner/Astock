<template>
  <div class="container">
    <a-card title="全球资产价格水位" class="section-card">
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
  import { Tag } from '@arco-design/web-vue';
  import type { TableColumnData, TableData } from '@arco-design/web-vue';
  import {
    fetchAssetPriceLevels,
    type AssetPriceLevelItem,
    type AssetPriceLevels,
  } from '@/api/analysis';

  /** 七姐妹 + SpaceX */
  const FOCUSED_TICKERS = new Set([
    'AAPL',
    'MSFT',
    'GOOGL',
    'AMZN',
    'NVDA',
    'META',
    'TSLA',
    'SPCX',
  ]);

  interface DividerRow {
    key: string;
    rowKind: 'divider';
    label: string;
  }

  type TableRow = (AssetPriceLevelItem & { key: string }) | DividerRow;

  const loading = ref(false);
  const levels = ref<AssetPriceLevels | null>(null);

  const metaText = computed(() => {
    if (!levels.value?.latest_trading_date) return '';
    return `最新数据日期 ${levels.value.latest_trading_date}`;
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

  const conclusionColor = (conclusion: string) => {
    if (conclusion === '待接入') return 'gray';
    if (conclusion === '接近历史高点') return 'arcoblue';
    if (conclusion === '适度回调') return 'gold';
    if (conclusion === '显著回调') return 'orangered';
    return 'red';
  };

  const isDividerRow = (record: TableRow): record is DividerRow =>
    'rowKind' in record && record.rowKind === 'divider';

  const toTableRow = (record: TableData): TableRow => record as TableRow;

  const isFocusedTicker = (ticker: string) => FOCUSED_TICKERS.has(ticker);

  const tableRows = computed<TableRow[]>(() => {
    const items = levels.value?.items ?? [];
    const stockItems = items.filter((item) => item.asset_type === 'stock');
    const pendingStocks = stockItems
      .filter((item) => item.data_pending)
      .map((item) => ({ ...item, key: item.ticker }));
    const normalStocks = stockItems
      .filter((item) => !item.data_pending)
      .sort((a, b) => (a.percentage_diff ?? 0) - (b.percentage_diff ?? 0))
      .map((item) => ({ ...item, key: item.ticker }));
    const stocks = [...pendingStocks, ...normalStocks];
    const metals = items
      .filter((item) => item.asset_type === 'metal')
      .sort((a, b) => (a.percentage_diff ?? 0) - (b.percentage_diff ?? 0))
      .map((item) => ({ ...item, key: item.ticker }));

    if (metals.length === 0) return stocks;

    return [
      ...stocks,
      { key: 'divider-metal', rowKind: 'divider', label: '贵金属' },
      ...metals,
    ];
  });

  const renderAssetCell = (record: AssetPriceLevelItem) => {
    return h('span', { class: 'asset-name-cell' }, [
      h('span', { class: 'asset-name-text' }, record.name),
      h('span', { class: 'asset-ticker-text' }, ` (${record.ticker})`),
      isFocusedTicker(record.ticker)
        ? h(
            Tag,
            {
              color: 'orangered',
              size: 'small',
              class: 'focus-tag',
              style: { marginLeft: '8px' },
            },
            () => '重点'
          )
        : null,
    ]);
  };

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
          return h('span', { class: 'section-divider-label' }, row.label);
        }
        return renderAssetCell(row);
      },
    },
    {
      title: '当前参考价',
      render: ({ record }) => {
        const row = toTableRow(record);
        if (isDividerRow(row)) return null;
        return formatPrice(row.current_price);
      },
    },
    {
      title: '历史最高价',
      render: ({ record }) => {
        const row = toTableRow(record);
        if (isDividerRow(row)) return null;
        return formatPrice(row.all_time_high);
      },
    },
    {
      title: '距最高点',
      render: ({ record }) => {
        const row = toTableRow(record);
        if (isDividerRow(row)) return null;
        return h(
          'span',
          { style: { color: pctColor(row.percentage_diff) } },
          formatPct(row.percentage_diff)
        );
      },
    },
    {
      title: '距最高天数',
      render: ({ record }) => {
        const row = toTableRow(record);
        if (isDividerRow(row)) return null;
        return row.ath_days ?? '--';
      },
    },
    {
      title: '日涨跌',
      render: ({ record }) => {
        const row = toTableRow(record);
        if (isDividerRow(row)) return null;
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
        if (isDividerRow(row)) return null;
        return h(
          'span',
          { style: { color: pctColor(row.weekly_change) } },
          formatPct(row.weekly_change)
        );
      },
    },
    {
      title: '结论',
      render: ({ record }) => {
        const row = toTableRow(record);
        if (isDividerRow(row)) return null;
        return h(
          Tag,
          { color: conclusionColor(row.conclusion) },
          () => row.conclusion
        );
      },
    },
  ];

  const loadLevels = async (forceRefresh = false) => {
    loading.value = true;
    try {
      const res = await fetchAssetPriceLevels(forceRefresh);
      levels.value = res.data;
    } finally {
      loading.value = false;
    }
  };

  onMounted(() => {
    loadLevels();
  });
</script>

<script lang="ts">
  export default {
    name: 'AssetPriceLevels',
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

  .asset-name-cell {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .focus-tag {
    color: #fadb14;
    font-size: 15px;
    font-weight: 600;
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
