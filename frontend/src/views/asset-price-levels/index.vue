<template>
  <div class="page-container">
    <a-card title="全球资产价格水位" class="section-card">
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
  import { Tag } from '@arco-design/web-vue';
  import type { TableColumnData } from '@arco-design/web-vue';
  import {
    fetchAssetPriceLevels,
    type AssetPriceLevelItem,
  } from '@/api/analysis';
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
    name: 'AssetPriceLevels',
  });

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

  type DividerRow = BaseDividerRow;

  type TableRow = (AssetPriceLevelItem & { key: string }) | DividerRow;

  const {
    loading,
    data: levels,
    run: loadLevels,
  } = useAsyncRequest((forceRefresh?: boolean) =>
    fetchAssetPriceLevels(forceRefresh ?? false)
  );

  const metaText = computed(() => {
    if (!levels.value?.latest_trading_date) return '';
    return `最新数据日期 ${levels.value.latest_trading_date}`;
  });

  const conclusionColor = (conclusion: string) => {
    if (conclusion === '待接入') return 'gray';
    if (conclusion === '接近历史高点') return 'arcoblue';
    if (conclusion === '适度回调') return 'gold';
    if (conclusion === '显著回调') return 'orangered';
    return 'red';
  };

  const isFocusedTicker = (ticker: string) => FOCUSED_TICKERS.has(ticker);

  const sortByPercentageDiff = (
    a: AssetPriceLevelItem,
    b: AssetPriceLevelItem
  ) => (a.percentage_diff ?? 0) - (b.percentage_diff ?? 0);

  const tableRows = computed<TableRow[]>(() => {
    const items = levels.value?.items ?? [];
    const groups = {
      pendingStocks: [] as TableRow[],
      normalStocks: [] as AssetPriceLevelItem[],
      metals: [] as AssetPriceLevelItem[],
    };

    items.forEach((item) => {
      if (item.asset_type === 'metal') {
        groups.metals.push(item);
      } else if (item.asset_type === 'stock') {
        if (item.data_pending) {
          groups.pendingStocks.push({ ...item, key: item.ticker });
        } else {
          groups.normalStocks.push(item);
        }
      }
    });

    const stocks = [
      ...groups.pendingStocks,
      ...groups.normalStocks.sort(sortByPercentageDiff).map((item) => ({
        ...item,
        key: item.ticker,
      })),
    ];
    const metals = groups.metals.sort(sortByPercentageDiff).map((item) => ({
      ...item,
      key: item.ticker,
    }));

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

  const columns: TableColumnData[] = [
    {
      title: '资产',
      render: ({ record }) => {
        const row = toTableRow<TableRow>(record);
        if (isDividerRow(row)) {
          return h('span', { class: 'section-divider-label' }, row.label);
        }
        return renderAssetCell(row);
      },
    },
    {
      title: '当前参考价',
      render: ({ record }) => {
        const row = toTableRow<TableRow>(record);
        if (isDividerRow(row)) return null;
        return formatPrice(row.current_price);
      },
    },
    {
      title: '历史最高价',
      render: ({ record }) => {
        const row = toTableRow<TableRow>(record);
        if (isDividerRow(row)) return null;
        return formatPrice(row.all_time_high);
      },
    },
    {
      title: '距最高点',
      render: ({ record }) => {
        const row = toTableRow<TableRow>(record);
        if (isDividerRow(row)) return null;
        return h(
          'span',
          { style: { color: getPercentColor(row.percentage_diff) } },
          formatPercent(row.percentage_diff)
        );
      },
    },
    {
      title: '距最高天数',
      render: ({ record }) => {
        const row = toTableRow<TableRow>(record);
        if (isDividerRow(row)) return null;
        return row.ath_days ?? '--';
      },
    },
    {
      title: '日涨跌',
      render: ({ record }) => {
        const row = toTableRow<TableRow>(record);
        if (isDividerRow(row)) return null;
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
        if (isDividerRow(row)) return null;
        return h(
          'span',
          { style: { color: getPercentColor(row.weekly_change) } },
          formatPercent(row.weekly_change)
        );
      },
    },
    {
      title: '结论',
      render: ({ record }) => {
        const row = toTableRow<TableRow>(record);
        if (isDividerRow(row)) return null;
        return h(
          Tag,
          { color: conclusionColor(row.conclusion) },
          () => row.conclusion
        );
      },
    },
  ];

  const { spanMethod, rowClass } = useDividerTable(columns);

  onMounted(() => {
    loadLevels();
  });
</script>

<style scoped lang="less">
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
</style>
