import { computed, type Ref } from 'vue';
import { useI18n } from 'vue-i18n';
import {
  macroLineOption,
  macroTooltipDataIndex,
  readCssVar,
  useMacroLineChart,
} from '@/hooks/use-macro-line-chart';
import { formatAmount } from '@/utils/format';
import downsampleLttb from './downsample';

/** 约一个自然年的交易日。更长区间降到这个密度，避免折线叠成色块。 */
const MAX_CHART_POINTS = 260;
const MAX_CHART_POINTS_MOBILE = 160;

export default function useTurnoverChart(
  chartEl: Ref<HTMLElement | null>,
  points: Ref<API.TurnoverSeriesItem[]>,
) {
  const { t, locale } = useI18n();

  const hasData = computed(() => points.value.length > 0);

  function buildOption({
    isDark,
    isMobile,
  }: {
    isDark: boolean;
    isMobile: boolean;
  }) {
    const seriesName = t('pages.turnoverRank.chart.series');
    const lineColor = readCssVar('--brand-6', '#1a4b8c');
    const sampled = downsampleLttb(
      points.value,
      isMobile ? MAX_CHART_POINTS_MOBILE : MAX_CHART_POINTS,
      (item) => item.turnover,
    );

    return macroLineOption({
      isDark,
      isMobile,
      colors: [lineColor],
      categories: sampled.map((item) => item.date),
      legend: [seriesName],
      showLegend: false,
      yAxisFormatter: (value) => formatAmount(value),
      grid: isMobile
        ? { left: 72, right: 12, top: 16, bottom: 28 }
        : { left: 88, right: 24, top: 20, bottom: 36 },
      tooltipFormatter: (params) => {
        const point = sampled[macroTooltipDataIndex(params)];
        if (!point) return '';
        const lines = [
          `${t('pages.turnoverRank.chart.tooltip.date')}: ${point.date}`,
          `${t('pages.turnoverRank.chart.tooltip.sh')}: ${formatAmount(
            point.sse_amount,
          )}`,
          `${t('pages.turnoverRank.chart.tooltip.sz')}: ${formatAmount(
            point.szse_amount,
          )}`,
          `${t('pages.turnoverRank.chart.tooltip.total')}: ${formatAmount(
            point.turnover,
          )}`,
        ];
        return lines.join('<br/>');
      },
      series: [
        {
          name: seriesName,
          type: 'line',
          data: sampled.map((item) => item.turnover),
          showSymbol: false,
          smooth: 0.2,
          smoothMonotone: 'x',
          sampling: 'lttb',
          lineStyle: { width: 1.5 },
        },
      ],
    });
  }

  useMacroLineChart(chartEl, hasData, buildOption, [points, locale]);

  return { hasData };
}
