import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  watch,
  type Ref,
} from 'vue';
import { useDark, useResizeObserver } from '@vueuse/core';
import { useI18n } from 'vue-i18n';
import * as echarts from 'echarts/core';
import { LineChart } from 'echarts/charts';
import {
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import type { CnMacroPointItem } from '@/api/analysis';

echarts.use([
  LineChart,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
  CanvasRenderer,
]);

export type CnMacroChartKind = 'cpiPpi' | 'pmi' | 'consumer';

/** 中国宏观专用配色：青绿 + 靛紫，区别于美国宏观的红/深蓝 */
const CN_MACRO_COLORS = {
  primary: '#0d9488',
  secondary: '#4f46e5',
} as const;

function formatNumber(value: number | null | undefined, suffix = ''): string {
  if (value == null || Number.isNaN(value)) return '—';
  return `${value.toFixed(2)}${suffix}`;
}

export default function useCnMacroChart(
  chartEl: Ref<HTMLElement | null>,
  points: Ref<CnMacroPointItem[]>,
  kind: CnMacroChartKind,
) {
  const { t, locale } = useI18n();
  const isDark = useDark({
    selector: 'body',
    attribute: 'arco-theme',
    valueDark: 'dark',
    valueLight: 'light',
    storageKey: 'arco-theme',
  });

  let chart: echarts.ECharts | null = null;

  const hasData = computed(() => {
    if (points.value.length === 0) return false;
    return points.value.some((p) => {
      if (kind === 'cpiPpi') return p.cpi_yoy != null || p.ppi_yoy != null;
      if (kind === 'pmi') {
        return p.pmi_manufacturing != null || p.pmi_non_manufacturing != null;
      }
      return p.consumer_confidence != null;
    });
  });

  function buildOption(): echarts.EChartsCoreOption {
    const textColor = isDark.value
      ? 'rgba(255,255,255,0.7)'
      : 'rgba(0,0,0,0.65)';
    const splitLine = isDark.value
      ? 'rgba(255,255,255,0.12)'
      : 'rgba(0,0,0,0.08)';
    const colorA = CN_MACRO_COLORS.primary;
    const colorB = CN_MACRO_COLORS.secondary;
    const categories = points.value.map((p) => p.period);

    if (kind === 'cpiPpi') {
      const cpiName = t('pages.cnMacroData.series.cpi');
      const ppiName = t('pages.cnMacroData.series.ppi');
      return {
        animation: false,
        color: [colorB, colorA],
        textStyle: {
          color: textColor,
          fontFamily: 'var(--font-family-sans)',
        },
        legend: {
          top: 8,
          data: [cpiName, ppiName],
          textStyle: { color: textColor },
        },
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'cross' },
          formatter: (params: unknown) => {
            const items = Array.isArray(params) ? params : [params];
            const first = items[0] as { dataIndex?: number } | undefined;
            const idx = first?.dataIndex ?? 0;
            const point = points.value[idx];
            if (!point) return '';
            return [
              `${t('pages.cnMacroData.tooltip.period')}: ${point.period}`,
              `${t('pages.cnMacroData.tooltip.cpi')}: ${formatNumber(
                point.cpi_yoy,
                '%',
              )}`,
              `${t('pages.cnMacroData.tooltip.ppi')}: ${formatNumber(
                point.ppi_yoy,
                '%',
              )}`,
            ].join('<br/>');
          },
        },
        grid: { left: 56, right: 24, top: 56, bottom: 40 },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          data: categories,
          axisLabel: { color: textColor, hideOverlap: true },
          axisLine: { lineStyle: { color: splitLine } },
        },
        yAxis: {
          type: 'value',
          axisLabel: {
            color: textColor,
            formatter: (v: number) => `${v}%`,
          },
          splitLine: { lineStyle: { color: splitLine, type: 'dashed' } },
        },
        series: [
          {
            name: cpiName,
            type: 'line',
            data: points.value.map((p) => p.cpi_yoy),
            showSymbol: true,
            symbolSize: 6,
            connectNulls: false,
            lineStyle: { width: 2 },
          },
          {
            name: ppiName,
            type: 'line',
            data: points.value.map((p) => p.ppi_yoy),
            showSymbol: true,
            symbolSize: 6,
            connectNulls: false,
            lineStyle: { width: 2 },
          },
        ],
      };
    }

    if (kind === 'pmi') {
      const mfgName = t('pages.cnMacroData.series.pmiMfg');
      const nonMfgName = t('pages.cnMacroData.series.pmiNonMfg');
      const boomBust = t('pages.cnMacroData.series.boomBust');
      return {
        animation: false,
        color: [colorA, colorB],
        textStyle: {
          color: textColor,
          fontFamily: 'var(--font-family-sans)',
        },
        legend: {
          top: 8,
          data: [mfgName, nonMfgName],
          textStyle: { color: textColor },
        },
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'cross' },
          formatter: (params: unknown) => {
            const items = Array.isArray(params) ? params : [params];
            const first = items[0] as { dataIndex?: number } | undefined;
            const idx = first?.dataIndex ?? 0;
            const point = points.value[idx];
            if (!point) return '';
            return [
              `${t('pages.cnMacroData.tooltip.period')}: ${point.period}`,
              `${t('pages.cnMacroData.tooltip.pmiMfg')}: ${formatNumber(
                point.pmi_manufacturing,
              )}`,
              `${t('pages.cnMacroData.tooltip.pmiNonMfg')}: ${formatNumber(
                point.pmi_non_manufacturing,
              )}`,
            ].join('<br/>');
          },
        },
        grid: { left: 56, right: 24, top: 56, bottom: 40 },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          data: categories,
          axisLabel: { color: textColor, hideOverlap: true },
          axisLine: { lineStyle: { color: splitLine } },
        },
        yAxis: {
          type: 'value',
          scale: true,
          axisLabel: { color: textColor },
          splitLine: { lineStyle: { color: splitLine, type: 'dashed' } },
        },
        series: [
          {
            name: mfgName,
            type: 'line',
            data: points.value.map((p) => p.pmi_manufacturing),
            showSymbol: false,
            connectNulls: false,
            lineStyle: { width: 2 },
          },
          {
            name: nonMfgName,
            type: 'line',
            data: points.value.map((p) => p.pmi_non_manufacturing),
            showSymbol: false,
            connectNulls: false,
            lineStyle: { width: 2 },
          },
          {
            // 独立序列承载荣枯线，不进 legend，取消制造/非制造选中时仍保留
            name: boomBust,
            type: 'line',
            data: [],
            silent: true,
            tooltip: { show: false },
            markLine: {
              silent: true,
              symbol: 'none',
              label: {
                formatter: boomBust,
                position: 'insideEndTop',
                color: textColor,
              },
              lineStyle: {
                type: 'dashed',
                color: isDark.value
                  ? 'rgba(255,255,255,0.45)'
                  : 'rgba(0,0,0,0.35)',
                width: 1.5,
              },
              data: [{ yAxis: 50 }],
            },
          },
        ],
      };
    }

    const consumerName = t('pages.cnMacroData.series.consumer');
    return {
      animation: false,
      color: [colorA],
      textStyle: {
        color: textColor,
        fontFamily: 'var(--font-family-sans)',
      },
      legend: {
        top: 8,
        data: [consumerName],
        textStyle: { color: textColor },
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        formatter: (params: unknown) => {
          const items = Array.isArray(params) ? params : [params];
          const first = items[0] as { dataIndex?: number } | undefined;
          const idx = first?.dataIndex ?? 0;
          const point = points.value[idx];
          if (!point) return '';
          return [
            `${t('pages.cnMacroData.tooltip.period')}: ${point.period}`,
            `${t('pages.cnMacroData.tooltip.consumer')}: ${formatNumber(
              point.consumer_confidence,
            )}`,
          ].join('<br/>');
        },
      },
      grid: { left: 56, right: 24, top: 56, bottom: 40 },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: categories,
        axisLabel: { color: textColor, hideOverlap: true },
        axisLine: { lineStyle: { color: splitLine } },
      },
      yAxis: {
        type: 'value',
        scale: true,
        axisLabel: { color: textColor },
        splitLine: { lineStyle: { color: splitLine, type: 'dashed' } },
      },
      series: [
        {
          name: consumerName,
          type: 'line',
          data: points.value.map((p) => p.consumer_confidence),
          showSymbol: false,
          connectNulls: false,
          lineStyle: { width: 2 },
        },
      ],
    };
  }

  function ensureChart() {
    if (!chartEl.value) return;
    if (!chart) {
      chart = echarts.init(chartEl.value);
    }
    chart.setOption(buildOption(), true);
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

  watch([points, isDark, locale], () => {
    render();
  });

  onMounted(() => {
    render();
  });

  onBeforeUnmount(() => {
    disposeChart();
  });

  return { hasData };
}
