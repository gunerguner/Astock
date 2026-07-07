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
  import { computed, h, onMounted } from 'vue';
  import { useI18n } from 'vue-i18n';
  import type { TableColumnData } from '@arco-design/web-vue';
  import { fetchMarketOverview, type MarketOverviewItem } from '@/api/analysis';
  import useAsyncRequest from '@/hooks/async-request';
  import {
    isDividerRow,
    toTableRow,
    useDividerTable,
    type BaseDividerRow,
  } from '@/hooks/grouped-table';
  import {
    formatPercent,
    formatPrice,
    getPercentClass,
    numClass,
  } from '@/utils/format';
  import renderAssetNameWithTooltip from '@/utils/render-asset-cell';
  import useTableScroll from '@/utils/table';

  const { t } = useI18n();
  const tableScroll = useTableScroll();

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
    return t('common.metaLatestDate', {
      date: overview.value.latest_trading_date,
    });
  });

  const formatPeriod = (start: string | null, end: string | null) => {
    if (!start || !end) return '';
    if (start === end) return start;
    return `${start} ${t('pages.marketOverview.periodTo')} ${end}`;
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

  const columns = computed<TableColumnData[]>(() => [
    {
      title: t('pages.marketOverview.columns.asset'),
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
        return renderAssetNameWithTooltip(row.name, row.code);
      },
    },
    {
      title: t('pages.marketOverview.columns.currentPrice'),
      align: 'right',
      render: ({ record }) => {
        const row = toTableRow<TableRow>(record);
        if (isDividerRow(row)) return null;
        if (row.error) return t('pages.marketOverview.fetchError');
        return h(
          'span',
          { class: `num-price ${numClass(row.current_price)}` },
          formatPrice(row.current_price)
        );
      },
    },
    {
      title: t('pages.marketOverview.columns.dailyChange'),
      align: 'right',
      render: ({ record }) => {
        const row = toTableRow<TableRow>(record);
        if (isDividerRow(row) || row.error) return null;
        return h(
          'span',
          { class: getPercentClass(row.daily_change) },
          formatPercent(row.daily_change)
        );
      },
    },
    {
      title: t('pages.marketOverview.columns.weeklyChange'),
      align: 'right',
      render: ({ record }) => {
        const row = toTableRow<TableRow>(record);
        if (isDividerRow(row) || row.error) return null;
        return h(
          'span',
          { class: getPercentClass(row.weekly_change) },
          formatPercent(row.weekly_change)
        );
      },
    },
  ]);

  const { spanMethod, rowClass } = useDividerTable(columns);

  onMounted(() => {
    loadOverview();
  });
</script>
