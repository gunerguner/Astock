import { computed, type Ref } from 'vue';
import { useI18n } from 'vue-i18n';
import * as echarts from 'echarts/core';
import { LineChart } from 'echarts/charts';
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { useMacroLineChart } from '@/hooks/use-macro-line-chart';

echarts.use([
  LineChart,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  CanvasRenderer,
]);

function readCssVar(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback;
  const value = getComputedStyle(document.body).getPropertyValue(name).trim();
  return value || fallback;
}

function formatNumber(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  return `${value.toFixed(2)}%`;
}

export default function useUsMacroChart(
  chartEl: Ref<HTMLElement | null>,
  points: Ref<API.UsMacroPointItem[]>,
) {
  const { t, locale } = useI18n();

  const hasData = computed(() => points.value.length > 0);

  function buildOption({
    isDark,
  }: {
    isDark: boolean;
  }): echarts.EChartsCoreOption {
    const cpiName = t('pages.usMacroData.series.cpi');
    const fedName = t('pages.usMacroData.series.fedRate');
    const textColor = isDark ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.65)';
    const splitLine = isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.08)';
    const cpiColor = readCssVar('--up-color', '#e0463e');
    const fedColor = readCssVar('--brand-6', '#1a4b8c');

    const categories = points.value.map((p) => p.period);
    const cpiData = points.value.map((p) => p.cpi_yoy);
    const fedData = points.value.map((p) => p.fed_rate_upper);

    return {
      animation: false,
      color: [cpiColor, fedColor],
      textStyle: {
        color: textColor,
        fontFamily: 'var(--font-family-sans)',
      },
      legend: {
        top: 8,
        data: [cpiName, fedName],
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
            `${t('pages.usMacroData.tooltip.period')}: ${point.period}`,
            `${t('pages.usMacroData.tooltip.cpi')}: ${formatNumber(point.cpi_yoy)}`,
            `${t('pages.usMacroData.tooltip.fedRate')}: ${formatNumber(
              point.fed_rate_upper,
            )}`,
          ].join('<br/>');
        },
      },
      grid: {
        left: 56,
        right: 24,
        top: 56,
        bottom: 40,
      },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: categories,
        axisLabel: {
          color: textColor,
          hideOverlap: true,
        },
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
          data: cpiData,
          showSymbol: true,
          symbolSize: 6,
          connectNulls: false,
          lineStyle: { width: 2 },
        },
        {
          name: fedName,
          type: 'line',
          step: 'end',
          data: fedData,
          showSymbol: false,
          connectNulls: true,
          lineStyle: { width: 2 },
        },
      ],
    };
  }

  useMacroLineChart(chartEl, hasData, buildOption, [points, locale]);

  return { hasData };
}
