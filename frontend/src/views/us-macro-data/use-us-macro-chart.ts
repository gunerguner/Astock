import { computed, type Ref } from 'vue';
import { useI18n } from 'vue-i18n';
import {
  formatMacroNumber,
  macroLineOption,
  macroTooltipDataIndex,
  useMacroLineChart,
} from '@/hooks/use-macro-line-chart';

function readCssVar(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback;
  const value = getComputedStyle(document.body).getPropertyValue(name).trim();
  return value || fallback;
}

export default function useUsMacroChart(
  chartEl: Ref<HTMLElement | null>,
  points: Ref<API.UsMacroPointItem[]>,
) {
  const { t, locale } = useI18n();

  const hasData = computed(() => points.value.length > 0);

  function buildOption({ isDark }: { isDark: boolean }) {
    const cpiName = t('pages.usMacroData.series.cpi');
    const fedName = t('pages.usMacroData.series.fedRate');
    const cpiColor = readCssVar('--up-color', '#e0463e');
    const fedColor = readCssVar('--brand-6', '#1a4b8c');

    return macroLineOption({
      isDark,
      colors: [cpiColor, fedColor],
      categories: points.value.map((p) => p.period),
      legend: [cpiName, fedName],
      yAxisPercent: true,
      tooltipFormatter: (params) => {
        const point = points.value[macroTooltipDataIndex(params)];
        if (!point) return '';
        return [
          `${t('pages.usMacroData.tooltip.period')}: ${point.period}`,
          `${t('pages.usMacroData.tooltip.cpi')}: ${formatMacroNumber(point.cpi_yoy, '%')}`,
          `${t('pages.usMacroData.tooltip.fedRate')}: ${formatMacroNumber(
            point.fed_rate_upper,
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
          name: fedName,
          type: 'line',
          step: 'end',
          data: points.value.map((p) => p.fed_rate_upper),
          showSymbol: false,
          connectNulls: true,
          lineStyle: { width: 2 },
        },
      ],
    });
  }

  useMacroLineChart(chartEl, hasData, buildOption, [points, locale]);

  return { hasData };
}
