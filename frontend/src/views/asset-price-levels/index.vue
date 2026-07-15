<template>
  <div class="page-container">
    <a-card :title="$t('pages.assetPriceLevels.title')" class="section-card">
      <template #extra>
        <span v-if="metaText" class="meta-text">{{ metaText }}</span>
      </template>
      <a-table
        :columns="columns"
        :data="tableRows"
        :loading="loading"
        :pagination="false"
        :scroll="tableScroll"
        :span-method="spanMethod"
        :row-class="rowClass"
        row-key="key"
      />
    </a-card>
  </div>
</template>

<script lang="ts" setup>
  import { computed, h } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { Tag } from '@arco-design/web-vue';
  import type { TableColumnData, TableData } from '@arco-design/web-vue';
  import {
    fetchAssetPriceLevels,
    isPriceLevelPending,
    type PriceLevelDataItem,
    type PriceLevelRow
  } from '@/api/analysis';
  import useAsyncRequest from '@/hooks/async-request';
  import usePageRefresh from '@/hooks/use-page-refresh';
  import {
    isDividerRow,
    toTableRow,
    useDividerTable,
    type BaseDividerRow
  } from '@/hooks/grouped-table';
  import { CONCLUSION_I18N_KEYS } from '@/utils/format';
  import renderAssetNameWithTooltip from '@/utils/render-asset-cell';
  import {
    renderNumCell,
    renderPendingDash,
    renderPercentCell,
    renderPlainPriceCell,
    renderPriceCell
  } from '@/utils/table-cells';
  import { formatLatestDateMeta } from '@/utils/sync-meta';
  import useTableScroll from '@/hooks/use-table-scroll';

  const { t } = useI18n();
  const tableScroll = useTableScroll();

  defineOptions({
    name: 'AssetPriceLevels'
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
    'SPCX'
  ]);

  type DividerRow = BaseDividerRow;
  type TableRow = (PriceLevelRow & { key: string }) | DividerRow;

  const {
    loading,
    data: levels,
    run: loadLevels
  } = useAsyncRequest((forceRefresh?: boolean) =>
    fetchAssetPriceLevels(forceRefresh ?? false)
  );

  const metaText = computed(() =>
    formatLatestDateMeta(levels.value?.latest_trading_date)
  );

  const conclusionColor = (conclusion: string) => {
    if (conclusion === 'pending') return 'gray';
    if (conclusion === 'nearAth') return 'arcoblue';
    if (conclusion === 'moderatePullback') return 'gold';
    if (conclusion === 'significantPullback') return 'orangered';
    return 'red';
  };

  const isFocusedTicker = (ticker: string) => FOCUSED_TICKERS.has(ticker);

  const sortByPercentageDiff = (a: PriceLevelDataItem, b: PriceLevelDataItem) =>
    a.percentage_diff - b.percentage_diff;

  const tableRows = computed<TableRow[]>(() => {
    const items = levels.value?.items ?? [];
    const groups = {
      pendingStocks: [] as TableRow[],
      normalStocks: [] as PriceLevelDataItem[],
      metals: [] as PriceLevelDataItem[]
    };

    items.forEach((item) => {
      if (isPriceLevelPending(item)) {
        if (item.asset_type === 'stock') {
          groups.pendingStocks.push({ ...item, key: item.ticker });
        }
        return;
      }
      if (item.asset_type === 'metal') {
        groups.metals.push(item);
      } else {
        groups.normalStocks.push(item);
      }
    });

    const stocks = [
      ...groups.pendingStocks,
      ...groups.normalStocks.sort(sortByPercentageDiff).map((item) => ({
        ...item,
        key: item.ticker
      }))
    ];
    const metals = groups.metals.sort(sortByPercentageDiff).map((item) => ({
      ...item,
      key: item.ticker
    }));

    if (metals.length === 0) return stocks;

    return [
      ...stocks,
      {
        key: 'divider-metal',
        rowKind: 'divider',
        label: t('pages.assetPriceLevels.metalDivider')
      },
      ...metals
    ];
  });

  const renderAssetCell = (record: PriceLevelRow) => {
    return renderAssetNameWithTooltip(record.name, record.ticker, () =>
      isFocusedTicker(record.ticker)
        ? h(
            Tag,
            {
              color: 'arcoblue',
              size: 'small',
              class: 'focus-tag',
              style: { marginLeft: '8px' }
            },
            () => t('pages.assetPriceLevels.focusedTag')
          )
        : null
    );
  };

  const guardDataRow = (record: TableData) => {
    const row = toTableRow<TableRow>(record);
    if (isDividerRow(row)) {
      return null;
    }
    if (isPriceLevelPending(row)) {
      return 'pending' as const;
    }
    return row;
  };

  const columns = computed<TableColumnData[]>(() => [
    {
      title: t('pages.assetPriceLevels.columns.asset'),
      render: ({ record }) => {
        const row = toTableRow<TableRow>(record);
        if (isDividerRow(row)) {
          return h('span', { class: 'section-divider-label' }, row.label);
        }
        return renderAssetCell(row);
      }
    },
    {
      title: t('pages.assetPriceLevels.columns.currentPrice'),
      align: 'right',
      render: ({ record }) => {
        const row = guardDataRow(record);
        if (!row) return null;
        if (row === 'pending') return renderPendingDash();
        return renderPriceCell(row.current_price);
      }
    },
    {
      title: t('pages.assetPriceLevels.columns.athPrice'),
      align: 'right',
      render: ({ record }) => {
        const row = guardDataRow(record);
        if (!row) return null;
        if (row === 'pending') return renderPendingDash();
        return renderPlainPriceCell(row.all_time_high);
      }
    },
    {
      title: t('pages.assetPriceLevels.columns.athDiff'),
      align: 'right',
      render: ({ record }) => {
        const row = guardDataRow(record);
        if (!row) return null;
        if (row === 'pending') return renderPendingDash();
        return renderPercentCell(row.percentage_diff);
      }
    },
    {
      title: t('pages.assetPriceLevels.columns.athDays'),
      align: 'right',
      render: ({ record }) => {
        const row = guardDataRow(record);
        if (!row) return null;
        if (row === 'pending') return renderPendingDash();
        return renderNumCell(String(row.ath_days));
      }
    },
    {
      title: t('pages.assetPriceLevels.columns.dailyChange'),
      align: 'right',
      render: ({ record }) => {
        const row = guardDataRow(record);
        if (!row || row === 'pending') return null;
        return renderPercentCell(row.daily_change);
      }
    },
    {
      title: t('pages.assetPriceLevels.columns.weeklyChange'),
      align: 'right',
      render: ({ record }) => {
        const row = guardDataRow(record);
        if (!row || row === 'pending') return null;
        return renderPercentCell(row.weekly_change);
      }
    },
    {
      title: t('pages.assetPriceLevels.columns.conclusion'),
      render: ({ record }) => {
        const row = guardDataRow(record);
        if (!row || row === 'pending') return null;
        const conclusionKey = CONCLUSION_I18N_KEYS[row.conclusion];
        const label = conclusionKey ? t(conclusionKey) : row.conclusion;
        return h(Tag, { color: conclusionColor(row.conclusion) }, () => label);
      }
    }
  ]);

  const { spanMethod, rowClass } = useDividerTable(columns);

  usePageRefresh(() => loadLevels(true), {
    initialLoad: () => loadLevels()
  });
</script>
