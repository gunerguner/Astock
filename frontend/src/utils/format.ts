import type { PriceLevelConclusion } from '@/api/analysis';
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

export function formatAmount(value: number): string {
  const matched = getAmountUnits().find(([, base]) => Math.abs(value) >= base);
  if (matched) {
    const [label, base] = matched;
    return `${(value / base).toFixed(2)}${label}`;
  }
  return `${value.toFixed(0)}${t('common.unit.yuan')}`;
}

export function formatPoint(value: number | null): string {
  if (value === null) {
    return '-';
  }
  return value.toFixed(2);
}

export function formatPrice(value: number, digits = 2): string {
  return value.toFixed(digits);
}

export function formatPercent(value: number | null): string {
  if (value === null) {
    return '--';
  }
  const prefix = value > 0 ? '+' : '';
  return `${prefix}${value.toFixed(2)}%`;
}

/** A 股语义：红涨绿跌 */
export function getPercentClass(value: number | null): string {
  if (value === null) {
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

export function numClass(value: number | null): string {
  if (value === null) {
    return 'num';
  }
  return value < 0 ? 'num num-negative' : 'num';
}

/** 后端返回结论 code，前端做 i18n 映射 */
export const CONCLUSION_I18N_KEYS: Record<PriceLevelConclusion, string> = {
  pending: 'pages.assetPriceLevels.conclusion.pending',
  nearAth: 'pages.assetPriceLevels.conclusion.nearAth',
  moderatePullback: 'pages.assetPriceLevels.conclusion.moderatePullback',
  significantPullback: 'pages.assetPriceLevels.conclusion.significantPullback',
  deepPullback: 'pages.assetPriceLevels.conclusion.deepPullback',
};
