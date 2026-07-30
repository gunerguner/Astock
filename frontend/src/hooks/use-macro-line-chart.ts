import {
  nextTick,
  onBeforeUnmount,
  onMounted,
  watch,
  type ComputedRef,
  type Ref,
  type WatchSource,
} from 'vue';
import { useDark, useResizeObserver } from '@vueuse/core';
import * as echarts from 'echarts/core';

export type MacroChartOptionBuilder = (ctx: {
  isDark: boolean;
}) => echarts.EChartsCoreOption;

/**
 * 宏观折线图共享生命周期：初始化 / 暗色 / resize / 渲染与销毁。
 * 具体 series / tooltip 由调用方通过 buildOption 提供。
 */
export function useMacroLineChart(
  chartEl: Ref<HTMLElement | null>,
  hasData: ComputedRef<boolean>,
  buildOption: MacroChartOptionBuilder,
  deps: WatchSource[] = [],
) {
  const isDark = useDark({
    selector: 'body',
    attribute: 'arco-theme',
    valueDark: 'dark',
    valueLight: 'light',
    storageKey: 'arco-theme',
  });

  let chart: echarts.ECharts | null = null;

  function ensureChart() {
    if (!chartEl.value) return;
    if (!chart) {
      chart = echarts.init(chartEl.value);
    }
    chart.setOption(buildOption({ isDark: isDark.value }), true);
  }

  function disposeChart() {
    chart?.dispose();
    chart = null;
  }

  function render() {
    nextTick(() => {
      if (!hasData.value) {
        disposeChart();
        return;
      }
      ensureChart();
    });
  }

  useResizeObserver(chartEl, () => {
    chart?.resize();
  });

  watch([hasData, isDark, ...deps], () => {
    render();
  });

  onMounted(() => {
    render();
  });

  onBeforeUnmount(() => {
    disposeChart();
  });

  return { isDark, render };
}
