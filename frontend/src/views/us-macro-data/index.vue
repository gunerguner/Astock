<template>
  <div class="page-container">
    <a-card :title="$t('pages.usMacroData.title')" class="section-card">
      <template #extra>
        <span v-if="metaText" class="meta-text">{{ metaText }}</span>
      </template>
      <AsyncState
        :loading="loading"
        :error="loadError"
        :has-data="hasData"
        :empty-text="$t('pages.usMacroData.noData')"
        :min-height="'var(--chart-height)'"
        :rows="9"
        @retry="loadMacro()"
      >
        <div ref="chartRef" class="chart-canvas" />
      </AsyncState>
    </a-card>
  </div>
</template>

<script lang="ts" setup>
  import { computed, ref } from 'vue';
  import { fetchUsMacroData } from '@/api/analysis';
  import AsyncState from '@/components/async-state/index.vue';
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
    error: loadError,
    run: loadMacro,
  } = useAsyncRequest(() => fetchUsMacroData());

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
  .page-container {
    --chart-height: 420px;
  }

  .chart-canvas {
    width: 100%;
    height: var(--chart-height);
  }

  @media (max-width: @screen-mobile-max) {
    .page-container {
      --chart-height: 320px;
    }
  }
</style>
