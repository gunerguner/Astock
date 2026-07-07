import i18n from '@/locale';

const { t, locale } = i18n.global;

/** 中文语境沿用万/亿/万亿（4 位一进制），英文语境改为 million/billion/trillion（3 位一进制） */
function getAmountUnits(): [string, number][] {
  if (locale.value === 'en-US') {
    return [
      [t('common.unit.trillion'), 1e12],
      [t('common.unit.billion'), 1e9],
      [t('common.unit.million'), 1e6],
    ];
  }
  return [
    [t('common.unit.trillion'), 1e12],
    [t('common.unit.billion'), 1e8],
    [t('common.unit.million'), 1e4],
  ];
}

export function formatAmount(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '-';
  }
  const matched = getAmountUnits().find(([, base]) => Math.abs(value) >= base);
  if (matched) {
    const [label, base] = matched;
    return `${(value / base).toFixed(2)}${label}`;
  }
  return `${value.toFixed(0)}${t('common.unit.yuan')}`;
}

export function formatPoint(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '-';
  }
  return value.toFixed(2);
}

export function formatPrice(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '--';
  }
  return value.toFixed(2);
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return '--';
  }
  const prefix = value > 0 ? '+' : '';
  return `${prefix}${value.toFixed(2)}%`;
}

/** A 股语义：红涨绿跌 */
export function getPercentClass(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return 'pct-cell num';
  }
  if (value > 0) {
    return 'pct-cell num pct-up';
  }
  if (value < 0) {
    return 'pct-cell num pct-down num-negative';
  }
  return 'pct-cell num pct-flat';
}

export function numClass(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return 'num';
  }
  return value < 0 ? 'num num-negative' : 'num';
}

export function formatPeriod(start: string, end: string): string {
  return `${start} ~ ${end}`;
}

/** 后端固定返回中文结论文案 → 稳定 i18n key */
export const CONCLUSION_I18N_KEYS: Record<string, string> = {
  待接入: 'pages.assetPriceLevels.conclusion.pending',
  接近历史高点: 'pages.assetPriceLevels.conclusion.nearAth',
  适度回调: 'pages.assetPriceLevels.conclusion.moderatePullback',
  显著回调: 'pages.assetPriceLevels.conclusion.significantPullback',
  深度回调: 'pages.assetPriceLevels.conclusion.deepPullback',
};
