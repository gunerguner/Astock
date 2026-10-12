import { describe, expect, test, vi } from 'vitest';

import formatSyncMeta, { formatLatestDateMeta } from '@/utils/sync-meta';

const { i18nMock } = vi.hoisted(() => ({
  i18nMock: {
    global: {
      t: vi.fn(
        (key: string, params?: Record<string, string>) =>
          `${key}:${params?.date ?? ''}`,
      ),
    },
  },
}));

vi.mock('@/locale', () => ({ default: i18nMock }));

describe('formatLatestDateMeta', () => {
  test('空值返回空串,不触发 i18n', () => {
    expect(formatLatestDateMeta(null)).toBe('');
    expect(formatLatestDateMeta(undefined)).toBe('');
    expect(i18nMock.global.t).not.toHaveBeenCalled();
  });

  test('有值时走 i18n 插值', () => {
    expect(formatLatestDateMeta('2026-10-04')).toBe(
      'common.metaLatestDate:2026-10-04',
    );
  });
});

describe('formatSyncMeta(多数据集合并展示)', () => {
  test('取各数据集中最新的数据日期', () => {
    expect(
      formatSyncMeta(
        {
          last_synced_date: '2026-09-01',
          last_synced_at: 'a',
          status: 'success',
        },
        {
          last_synced_date: '2026-10-04',
          last_synced_at: 'b',
          status: 'success',
        },
      ),
    ).toBe('common.metaLatestDate:2026-10-04');
  });

  test('过滤空数据集与空日期', () => {
    expect(
      formatSyncMeta(null, undefined, {
        last_synced_date: null,
        last_synced_at: null,
        status: null,
      }),
    ).toBe('');
  });

  test('全部为空返回空串', () => {
    expect(formatSyncMeta()).toBe('');
  });
});
