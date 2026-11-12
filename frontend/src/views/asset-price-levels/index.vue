<template>
  <div class="page-container">
    <a-card :title="$t('pages.assetPriceLevels.title')" class="section-card">
      <template #extra>
        <span v-if="metaText" class="meta-text">{{ metaText }}</span>
      </template>
      <AsyncState
        :loading="loading"
        :error="loadError"
        :has-data="levels !== null"
        :rows="10"
        :min-height="360"
        @retry="loadLevels()"
      >
        <PartialErrorAlert :errors="levels?.cache_errors ?? []" />
        <a-table
          :columns="columns"
          :data="tableRows"
          :loading="loading && levels !== null"
          :pagination="false"
          :scroll="tableScroll"
          :span-method="spanMethod"
          :row-class="rowClass"
          row-key="key"
        />
      </AsyncState>
    </a-card>
  </div>
</template>

<script lang="ts" setup>
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { fetchAssetPriceLevels, isPriceLevelPending } from '@/api/analysis';
  import AsyncState from '@/components/async-state/index.vue';
  import PartialErrorAlert from '@/components/partial-error-alert/index.vue';
  import useAsyncRequest from '@/hooks/async-request';
  import usePageRefresh from '@/hooks/use-page-refresh';
  import { useIsMobile } from '@/hooks/responsive';
  import useTableScroll from '@/hooks/use-table-scroll';
  import { useDividerTable } from '@/hooks/grouped-table';
  import { formatLatestDateMeta } from '@/utils/sync-meta';
  import buildAssetColumns, {
    type AssetTableRow,
    type ErrorRow,
  } from './columns';

  const { t } = useI18n();
  const isMobile = useIsMobile();
  const tableScroll = useTableScroll();

  defineOptions({
    name: 'AssetPriceLevels',
  });

  const {
    loading,
    data: levels,
    error: loadError,
    run: loadLevels,
  } = useAsyncRequest((forceRefresh?: boolean) =>
    fetchAssetPriceLevels(forceRefresh ?? false),
  );

  const metaText = computed(() =>
    formatLatestDateMeta(levels.value?.latest_trading_date),
  );

  const sortByPercentageDiff = (
    a: API.PriceLevelDataItem,
    b: API.PriceLevelDataItem,
  ) => a.percentage_diff - b.percentage_diff;

  const tableRows = computed<AssetTableRow[]>(() => {
    const items = levels.value?.items ?? [];
    const pendingStocks = items
      .filter(
        (item) => isPriceLevelPending(item) && item.asset_type === 'stock',
      )
      .map((item) => ({ ...item, key: item.ticker }));
    const settled = items.filter(
      (item): item is API.PriceLevelDataItem => !isPriceLevelPending(item),
    );
    const normalStocks = settled.filter((item) => item.asset_type !== 'metal');
    const metalItems = settled.filter((item) => item.asset_type === 'metal');

    const errorRows: ErrorRow[] = (levels.value?.cache_errors ?? []).map(
      (message) => {
        const ticker = message.split(':')[0]?.trim() || message;
        return {
          key: `error-${ticker}`,
          rowKind: 'error',
          ticker,
          name: ticker,
          message,
        };
      },
    );

    const stocks = [
      ...errorRows,
      ...pendingStocks,
      ...normalStocks.sort(sortByPercentageDiff).map((item) => ({
        ...item,
        key: item.ticker,
      })),
    ];
    const metals = metalItems.sort(sortByPercentageDiff).map((item) => ({
      ...item,
      key: item.ticker,
    }));

    if (metals.length === 0) return stocks;

    return [
      ...stocks,
      {
        key: 'divider-metal',
        rowKind: 'divider',
        label: t('pages.assetPriceLevels.metalDivider'),
      },
      ...metals,
    ];
  });

  const columns = computed(() => buildAssetColumns(t, isMobile.value));

  const { spanMethod, rowClass } = useDividerTable(columns);

  usePageRefresh(() => loadLevels(true), {
    initialLoad: () => loadLevels(),
  });
</script>
