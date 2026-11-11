import {
  nextTick,
  onActivated,
  onBeforeUnmount,
  onMounted,
  watch,
  type ComputedRef,
  type Ref,
  type WatchSource,
} from 'vue';
import { useDark, useResizeObserver } from '@vueuse/core';
import { LineChart, type LineSeriesOption } from 'echarts/charts';
import {
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
} from 'echarts/components';
import * as echarts from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { useIsMobile } from '@/hooks/responsive';

echarts.use([
  LineChart,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
  CanvasRenderer,
]);

export function formatMacroNumber(
  value: number | null | undefined,
  suffix = '',
): string {
  if (value == null || Number.isNaN(value)) return '—';
  return `${value.toFixed(2)}${suffix}`;
}

export function macroTooltipDataIndex(params: unknown): number {
  const items = Array.isArray(params) ? params : [params];
  const first = items[0] as { dataIndex?: number } | undefined;
  return first?.dataIndex ?? 0;
}

export function macroLineOption(options: {
  isDark: boolean;
  isMobile?: boolean;
  colors: string[];
  categories: string[];
  legend: string[];
  tooltipFormatter: (params: unknown) => string;
  yAxisPercent?: boolean;
  yAxisScale?: boolean;
  series: LineSeriesOption[];
}): echarts.EChartsCoreOption {
  const textColor = options.isDark
    ? 'rgba(255,255,255,0.7)'
    : 'rgba(0,0,0,0.65)';
  const splitLine = options.isDark
    ? 'rgba(255,255,255,0.12)'
    : 'rgba(0,0,0,0.08)';
  const compact = options.isMobile === true;
  const axisFont = compact ? { fontSize: 11 } : {};
  return {
    animation: false,
    color: options.colors,
    textStyle: {
      color: textColor,
      fontFamily: 'var(--font-family-sans)',
    },
    legend: {
      top: 8,
      data: options.legend,
      textStyle: { color: textColor, ...axisFont },
      ...(compact ? { type: 'scroll' as const } : {}),
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: options.tooltipFormatter,
    },
    grid: compact
      ? { left: 44, right: 12, top: 48, bottom: 32 }
      : { left: 56, right: 24, top: 56, bottom: 40 },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: options.categories,
      axisLabel: { color: textColor, hideOverlap: true, ...axisFont },
      axisLine: { lineStyle: { color: splitLine } },
    },
    yAxis: {
      type: 'value',
      ...(options.yAxisScale ? { scale: true } : {}),
      axisLabel: {
        color: textColor,
        ...axisFont,
        ...(options.yAxisPercent ? { formatter: (v: number) => `${v}%` } : {}),
      },
      splitLine: { lineStyle: { color: splitLine, type: 'dashed' } },
    },
    series: options.series,
  };
}

export type MacroChartOptionBuilder = (ctx: {
  isDark: boolean;
  isMobile: boolean;
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
  const isMobile = useIsMobile();

  let chart: echarts.ECharts | null = null;

  function ensureChart() {
    if (!chartEl.value) return;
    if (!chart) {
      chart = echarts.init(chartEl.value);
    }
    chart.setOption(
      buildOption({ isDark: isDark.value, isMobile: isMobile.value }),
      true,
    );
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

  watch([hasData, isDark, isMobile, ...deps], () => {
    render();
  });

  onMounted(() => {
    render();
  });

  onActivated(() => {
    chart?.resize();
  });

  onBeforeUnmount(() => {
    disposeChart();
  });

  return { isDark, render };
}
