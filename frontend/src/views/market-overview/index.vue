<template>
  <div class="page-container">
    <a-card :title="$t('pages.marketOverview.title')" class="section-card">
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
  import type { TableColumnData, TableData } from '@arco-design/web-vue';
  import {
    fetchMarketOverview,
    isMarketOverviewError,
    type MarketOverviewDataItem,
    type MarketOverviewRow,
  } from '@/api/analysis';
  import useAsyncRequest from '@/hooks/async-request';
  import usePageRefresh from '@/hooks/use-page-refresh';
  import {
    isDividerRow,
    toTableRow,
    useDividerTable,
    type BaseDividerRow,
  } from '@/hooks/grouped-table';
  import renderAssetNameWithTooltip from '@/utils/render-asset-cell';
  import { renderPercentCell, renderPriceCell } from '@/utils/table-cells';
  import { formatLatestDateMeta } from '@/utils/sync-meta';
  import useTableScroll from '@/hooks/use-table-scroll';

  const { t } = useI18n();
  const tableScroll = useTableScroll();

  defineOptions({
    name: 'MarketOverview',
  });

  interface DividerRow extends BaseDividerRow {
    periodText: string;
  }

  type TableRow = (MarketOverviewRow & { rowKind?: 'data' }) | DividerRow;

  const {
    loading,
    data: overview,
    run: loadOverview,
  } = useAsyncRequest((forceRefresh?: boolean) =>
    fetchMarketOverview(forceRefresh ?? false),
  );

  const metaText = computed(() =>
    formatLatestDateMeta(overview.value?.latest_trading_date),
  );

  const formatPeriod = (start: string | null, end: string | null) => {
    if (!start || !end) return '';
    if (start === end) return start;
    return `${start} ${t('pages.marketOverview.periodTo')} ${end}`;
  };

  /** 债券、汇率展示到小数点后 3 位 */
  const priceDigitsForRow = (key: string) =>
    key.startsWith('bonds:') || key.startsWith('forex:') ? 3 : 2;

  const tableRows = computed<TableRow[]>(() => {
    const categories = overview.value?.categories ?? [];
    const rows: TableRow[] = [];

    categories.forEach((cat) => {
      const validItems = cat.items.filter(
        (item): item is MarketOverviewDataItem => !isMarketOverviewError(item),
      );
      const periodStarts = validItems
        .map((item) => item.period_start)
        .filter((value): value is string => Boolean(value));
      const periodEnds = validItems
        .map((item) => item.period_end)
        .filter((value): value is string => Boolean(value));
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

  const guardDataRow = (record: TableData) => {
    const row = toTableRow<TableRow>(record);
    if (isDividerRow(row)) {
      return null;
    }
    if (isMarketOverviewError(row)) {
      return 'error' as const;
    }
    return row;
  };

  const columns = computed<TableColumnData[]>(() => [
    {
      title: t('pages.marketOverview.columns.asset'),
      render: ({ record }: { record: TableData }) => {
        const row = toTableRow<TableRow>(record);
        if (isDividerRow(row)) {
          const suffix = row.periodText ? `（${row.periodText}）` : '';
          return h(
            'span',
            { class: 'section-divider-label' },
            `${row.label}${suffix}`,
          );
        }
        return renderAssetNameWithTooltip(row.name, row.code);
      },
    },
    {
      title: t('pages.marketOverview.columns.currentPrice'),
      align: 'right',
      render: ({ record }: { record: TableData }) => {
        const row = guardDataRow(record);
        if (!row) return null;
        if (row === 'error') {
          return t('pages.marketOverview.fetchError');
        }
        return renderPriceCell(row.current_price, priceDigitsForRow(row.key));
      },
    },
    {
      title: t('pages.marketOverview.columns.dailyChange'),
      align: 'right',
      render: ({ record }: { record: TableData }) => {
        const row = guardDataRow(record);
        if (!row || row === 'error') return null;
        return renderPercentCell(row.daily_change);
      },
    },
    {
      title: t('pages.marketOverview.columns.weeklyChange'),
      align: 'right',
      render: ({ record }: { record: TableData }) => {
        const row = guardDataRow(record);
        if (!row || row === 'error') return null;
        return renderPercentCell(row.weekly_change);
      },
    },
  ]);

  const { spanMethod, rowClass } = useDividerTable(columns);

  // 管理员刷新后仅补落后项；概览由后端导入后预热，勿 force 全量打源
  usePageRefresh(() => loadOverview(false), {
    initialLoad: () => loadOverview(),
  });
</script>
