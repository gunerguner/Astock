<template>
  <div class="page-container">
    <a-card :title="$t('pages.cnMacroData.titleCpiPpi')" class="section-card">
      <template #extra>
        <span v-if="metaText" class="meta-text">{{ metaText }}</span>
      </template>
      <a-spin :loading="loading" class="chart-spin chart-spin-main">
        <div v-if="!loading && !cpiHasData" class="chart-empty">
          {{ $t('pages.cnMacroData.noData') }}
        </div>
        <div v-else ref="cpiChartRef" class="chart-canvas chart-canvas-main" />
      </a-spin>
    </a-card>

    <div class="chart-row">
      <a-card
        :title="$t('pages.cnMacroData.titlePmi')"
        class="section-card chart-row-item"
      >
        <a-spin :loading="loading" class="chart-spin chart-spin-half">
          <div
            v-if="!loading && !pmiHasData"
            class="chart-empty chart-empty-half"
          >
            {{ $t('pages.cnMacroData.noData') }}
          </div>
          <div
            v-else
            ref="pmiChartRef"
            class="chart-canvas chart-canvas-half"
          />
        </a-spin>
      </a-card>

      <a-card
        :title="$t('pages.cnMacroData.titleConsumer')"
        class="section-card chart-row-item"
      >
        <a-spin :loading="loading" class="chart-spin chart-spin-half">
          <div
            v-if="!loading && !consumerHasData"
            class="chart-empty chart-empty-half"
          >
            {{ $t('pages.cnMacroData.noData') }}
          </div>
          <div
            v-else
            ref="consumerChartRef"
            class="chart-canvas chart-canvas-half"
          />
        </a-spin>
      </a-card>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { computed, ref } from 'vue';
  import { fetchCnMacroData } from '@/api/analysis';
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
  .chart-row {
    display: flex;
    gap: 16px;
    margin-top: 16px;
  }

  .chart-row-item {
    flex: 1;
    min-width: 0;
  }

  .chart-spin {
    display: block;
    width: 100%;
  }

  .chart-spin-main {
    min-height: 360px;
  }

  .chart-spin-half {
    min-height: 300px;
  }

  .chart-canvas {
    width: 100%;
  }

  .chart-canvas-main {
    height: 360px;
  }

  .chart-canvas-half {
    height: 300px;
  }

  .chart-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--color-text-3);
    font-size: var(--fs-body);
  }

  .chart-empty,
  .chart-spin-main .chart-empty {
    min-height: 360px;
  }

  .chart-empty-half {
    min-height: 300px;
  }

  @media (max-width: 720px) {
    .chart-row {
      flex-direction: column;
    }
  }
</style>
