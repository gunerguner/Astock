<template>
  <div class="page-container">
    <a-card :title="$t('pages.usMacroData.title')" class="section-card">
      <template #extra>
        <span v-if="metaText" class="meta-text">{{ metaText }}</span>
      </template>
      <a-spin :loading="loading" class="chart-spin">
        <div v-if="!loading && !hasData" class="chart-empty">
          {{ $t('pages.usMacroData.noData') }}
        </div>
        <div v-else ref="chartRef" class="chart-canvas" />
      </a-spin>
    </a-card>
  </div>
</template>

<script lang="ts" setup>
  import { computed, ref } from 'vue';
  import { fetchUsMacroData } from '@/api/analysis';
  import useAsyncRequest from '@/hooks/async-request';
  import usePageRefresh from '@/hooks/use-page-refresh';
  import { formatLatestDateMeta } from '@/utils/sync-meta';
  import useUsMacroChart from './use-us-macro-chart';

  defineOptions({
    name: 'UsMacroData',
  });

  const chartRef = ref<HTMLElement | null>(null);

  const {
    loading,
    data: macro,
    run: loadMacro,
  } = useAsyncRequest(() => fetchUsMacroData('2020-06'));

  const points = computed<API.UsMacroPointItem[]>(
    () => macro.value?.points ?? [],
  );

  const metaText = computed(() =>
    formatLatestDateMeta(macro.value?.latest_period),
  );

  const { hasData } = useUsMacroChart(chartRef, points);

  usePageRefresh(() => loadMacro(), {
    initialLoad: () => loadMacro(),
  });
</script>

<style scoped lang="less">
  .chart-spin {
    display: block;
    width: 100%;
    min-height: 420px;
  }

  .chart-canvas {
    width: 100%;
    height: 420px;
  }

  .chart-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 420px;
    color: var(--color-text-3);
    font-size: var(--fs-body);
  }
</style>
