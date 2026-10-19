import { computed, type Ref } from 'vue';
import { useI18n } from 'vue-i18n';
import {
  formatMacroNumber,
  macroLineOption,
  macroTooltipDataIndex,
  useMacroLineChart,
} from '@/hooks/use-macro-line-chart';

export type CnMacroChartKind = 'cpiPpi' | 'pmi' | 'consumer';

/** 中国宏观专用配色：青绿 + 靛紫，区别于美国宏观的红/深蓝 */
const CN_MACRO_COLORS = {
  primary: '#0d9488',
  secondary: '#4f46e5',
} as const;

export default function useCnMacroChart(
  chartEl: Ref<HTMLElement | null>,
  points: Ref<API.CnMacroPointItem[]>,
  kind: CnMacroChartKind,
) {
  const { t, locale } = useI18n();

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

  function pointAt(params: unknown) {
    return points.value[macroTooltipDataIndex(params)];
  }

  function buildOption({ isDark }: { isDark: boolean }) {
    const colorA = CN_MACRO_COLORS.primary;
    const colorB = CN_MACRO_COLORS.secondary;
    const categories = points.value.map((p) => p.period);

    if (kind === 'cpiPpi') {
      const cpiName = t('pages.cnMacroData.series.cpi');
      const ppiName = t('pages.cnMacroData.series.ppi');
      return macroLineOption({
        isDark,
        colors: [colorB, colorA],
        categories,
        legend: [cpiName, ppiName],
        yAxisPercent: true,
        tooltipFormatter: (params) => {
          const point = pointAt(params);
          if (!point) return '';
          return [
            `${t('pages.cnMacroData.tooltip.period')}: ${point.period}`,
            `${t('pages.cnMacroData.tooltip.cpi')}: ${formatMacroNumber(
              point.cpi_yoy,
              '%',
            )}`,
            `${t('pages.cnMacroData.tooltip.ppi')}: ${formatMacroNumber(
              point.ppi_yoy,
              '%',
            )}`,
          ].join('<br/>');
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
      });
    }

    if (kind === 'pmi') {
      const mfgName = t('pages.cnMacroData.series.pmiMfg');
      const nonMfgName = t('pages.cnMacroData.series.pmiNonMfg');
      const boomBust = t('pages.cnMacroData.series.boomBust');
      return macroLineOption({
        isDark,
        colors: [colorA, colorB],
        categories,
        legend: [mfgName, nonMfgName],
        yAxisScale: true,
        tooltipFormatter: (params) => {
          const point = pointAt(params);
          if (!point) return '';
          return [
            `${t('pages.cnMacroData.tooltip.period')}: ${point.period}`,
            `${t('pages.cnMacroData.tooltip.pmiMfg')}: ${formatMacroNumber(
              point.pmi_manufacturing,
            )}`,
            `${t('pages.cnMacroData.tooltip.pmiNonMfg')}: ${formatMacroNumber(
              point.pmi_non_manufacturing,
            )}`,
          ].join('<br/>');
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
                color: isDark ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.65)',
              },
              lineStyle: {
                type: 'dashed',
                color: isDark ? 'rgba(255,255,255,0.45)' : 'rgba(0,0,0,0.35)',
                width: 1.5,
              },
              data: [{ yAxis: 50 }],
            },
          },
        ],
      });
    }

    const consumerName = t('pages.cnMacroData.series.consumer');
    return macroLineOption({
      isDark,
      colors: [colorA],
      categories,
      legend: [consumerName],
      yAxisScale: true,
      tooltipFormatter: (params) => {
        const point = pointAt(params);
        if (!point) return '';
        return [
          `${t('pages.cnMacroData.tooltip.period')}: ${point.period}`,
          `${t('pages.cnMacroData.tooltip.consumer')}: ${formatMacroNumber(
            point.consumer_confidence,
          )}`,
        ].join('<br/>');
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
    });
  }

  useMacroLineChart(chartEl, hasData, buildOption, [points, locale]);

  return { hasData };
}
