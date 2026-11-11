<template>
  <div class="page-container">
    <a-card :title="$t('pages.cnMacroData.titleCpiPpi')" class="section-card">
      <template #extra>
        <span v-if="metaText" class="meta-text">{{ metaText }}</span>
      </template>
      <AsyncState
        :loading="loading"
        :error="loadError"
        :has-data="cpiHasData"
        :empty-text="$t('pages.cnMacroData.noData')"
        :min-height="'var(--chart-height-main)'"
        @retry="loadMacro()"
      >
        <div ref="cpiChartRef" class="chart-canvas chart-canvas-main" />
      </AsyncState>
    </a-card>

    <div class="chart-row">
      <a-card
        :title="$t('pages.cnMacroData.titlePmi')"
        class="section-card chart-row-item"
      >
        <AsyncState
          :loading="loading"
          :error="loadError"
          :has-data="pmiHasData"
          :empty-text="$t('pages.cnMacroData.noData')"
          :min-height="'var(--chart-height-half)'"
          :stale-alert="false"
          @retry="loadMacro()"
        >
          <div ref="pmiChartRef" class="chart-canvas chart-canvas-half" />
        </AsyncState>
      </a-card>

      <a-card
        :title="$t('pages.cnMacroData.titleConsumer')"
        class="section-card chart-row-item"
      >
        <AsyncState
          :loading="loading"
          :error="loadError"
          :has-data="consumerHasData"
          :empty-text="$t('pages.cnMacroData.noData')"
          :min-height="'var(--chart-height-half)'"
          :stale-alert="false"
          @retry="loadMacro()"
        >
          <div ref="consumerChartRef" class="chart-canvas chart-canvas-half" />
        </AsyncState>
      </a-card>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { computed, ref } from 'vue';
  import { fetchCnMacroData } from '@/api/analysis';
  import AsyncState from '@/components/async-state/index.vue';
  import useAsyncRequest from '@/hooks/async-request';
  import usePageRefresh from '@/hooks/use-page-refresh';
  import { formatLatestDateMeta } from '@/utils/sync-meta';
  import useCnMacroChart from './use-cn-macro-chart';

  defineOptions({
    name: 'CnMacroData',
  });

  const cpiChartRef = ref<HTMLElement | null>(null);
  const pmiChartRef = ref<HTMLElement | null>(null);
  const consumerChartRef = ref<HTMLElement | null>(null);

  const {
    loading,
    data: macro,
    error: loadError,
    run: loadMacro,
  } = useAsyncRequest(() => fetchCnMacroData());

  const points = computed<API.CnMacroPointItem[]>(
    () => macro.value?.points ?? [],
  );

  const metaText = computed(() =>
    formatLatestDateMeta(macro.value?.latest_period),
  );

  const { hasData: cpiHasData } = useCnMacroChart(
    cpiChartRef,
    points,
    'cpiPpi',
  );
  const { hasData: pmiHasData } = useCnMacroChart(pmiChartRef, points, 'pmi');
  const { hasData: consumerHasData } = useCnMacroChart(
    consumerChartRef,
    points,
    'consumer',
  );

  usePageRefresh(() => loadMacro(), {
    initialLoad: () => loadMacro(),
  });
</script>

<style scoped lang="less">
  .page-container {
    --chart-height-main: 360px;
    --chart-height-half: 300px;
  }

  .chart-row {
    display: flex;
    gap: 16px;
    margin-top: 16px;
  }

  .chart-row-item {
    flex: 1;
    min-width: 0;
  }

  .chart-canvas {
    width: 100%;
  }

  .chart-canvas-main {
    height: var(--chart-height-main);
  }

  .chart-canvas-half {
    height: var(--chart-height-half);
  }

  @media (max-width: @screen-mobile-max) {
    .page-container {
      --chart-height-main: 300px;
      --chart-height-half: 260px;
    }

    .chart-row {
      flex-direction: column;
    }
  }
</style>
