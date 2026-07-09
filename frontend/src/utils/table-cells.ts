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

export function renderPriceCell(value: number | null | undefined) {
  return h(
    'span',
    { class: `num-price ${numClass(value)}` },
    formatPrice(value)
  );
}

export function renderPlainPriceCell(value: number | null | undefined) {
  return h('span', { class: numClass(value) }, formatPrice(value));
}

export function renderPercentCell(value: number | null | undefined) {
  return h('span', { class: getPercentClass(value) }, formatPercent(value));
}
