import { h } from 'vue';
import {
  formatPercent,
  formatPrice,
  getPercentClass,
  numClass,
} from '@/utils/format';

export function renderNumCell(text: string) {
  return h('span', { class: 'num' }, text);
}

export function renderPendingDash() {
  return renderNumCell('--');
}

/** 当前价等必有数值；缺数由上游 error/pending 行处理 */
export function renderPriceCell(value: number, digits = 2) {
  return h(
    'span',
    { class: `num-price ${numClass(value)}` },
    formatPrice(value, digits)
  );
}

export function renderPlainPriceCell(value: number) {
  return h('span', { class: numClass(value) }, formatPrice(value));
}

/** 日/周涨跌等：无对照基准则为 null，展示 -- */
export function renderPercentCell(value: number | null) {
  return h('span', { class: getPercentClass(value) }, formatPercent(value));
}
