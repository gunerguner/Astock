import { describe, expect, test, vi } from 'vitest';

import {
  formatAmount,
  formatPercent,
  formatPoint,
  getPercentClass,
  numClass,
} from '@/utils/format';

const { i18nState } = vi.hoisted(() => ({
  i18nState: { locale: 'zh-CN' as 'zh-CN' | 'en-US' },
}));

vi.mock('@/locale', () => ({
  default: {
    global: {
      locale: {
        // 稳定引用 + 动态 value,模拟 i18n ref 的响应性
        get value() {
          return i18nState.locale;
        },
      },
      t: (key: string) => {
        const zh: Record<string, string> = {
          'common.unit.trillion': '万亿',
          'common.unit.billion': '亿',
          'common.unit.million': '万',
          'common.unit.yuan': '元',
        };
        const en: Record<string, string> = {
          'common.unit.trillion': 'trillion',
          'common.unit.billion': 'billion',
          'common.unit.million': 'million',
          'common.unit.yuan': 'yuan',
        };
        const dict = i18nState.locale === 'en-US' ? en : zh;
        return dict[key] ?? key;
      },
    },
  },
}));

describe('formatPoint', () => {
  test('null 渲染为 -', () => {
    expect(formatPoint(null)).toBe('-');
  });

  test('数值保留两位小数', () => {
    expect(formatPoint(3124.567)).toBe('3124.57');
  });
});

describe('formatPercent', () => {
  test('null 渲染为 --', () => {
    expect(formatPercent(null)).toBe('--');
  });

  test('正值带 + 号与百分号', () => {
    expect(formatPercent(1.234)).toBe('+1.23%');
  });

  test('负值不带 + 号', () => {
    expect(formatPercent(-1.234)).toBe('-1.23%');
  });
});

describe('getPercentClass(A 股语义:红涨绿跌)', () => {
  test('涨跌平与空值分别映射样式类', () => {
    expect(getPercentClass(0.5)).toBe('pct-cell num pct-up');
    expect(getPercentClass(-0.5)).toBe('pct-cell num pct-down num-negative');
    expect(getPercentClass(0)).toBe('pct-cell num pct-flat');
    expect(getPercentClass(null)).toBe('pct-cell num');
  });
});

describe('numClass', () => {
  test('负数追加负值样式,空值仅基础类', () => {
    expect(numClass(-1)).toBe('num num-negative');
    expect(numClass(1)).toBe('num');
    expect(numClass(null)).toBe('num');
  });
});

describe('formatAmount(中文语境 4 位一进制)', () => {
  test('万亿/亿/万/元 按量级分档', () => {
    i18nState.locale = 'zh-CN';
    expect(formatAmount(2.5e12)).toBe('2.50万亿');
    expect(formatAmount(3.2e8)).toBe('3.20亿');
    expect(formatAmount(5e4)).toBe('5.00万');
    expect(formatAmount(123.45)).toBe('123元');
  });

  test('英文语境 3 位一进制', () => {
    i18nState.locale = 'en-US';
    expect(formatAmount(2.5e12)).toBe('2.50trillion');
    expect(formatAmount(3.2e9)).toBe('3.20billion');
    i18nState.locale = 'zh-CN';
  });
});
