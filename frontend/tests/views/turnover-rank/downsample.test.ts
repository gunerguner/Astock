import { describe, expect, test } from 'vitest';

import downsampleLttb from '@/views/turnover-rank/downsample';

describe('downsampleLttb', () => {
  test('不超过阈值时保持原序列', () => {
    const points = [1, 4, 2];
    expect(downsampleLttb(points, 3, (value) => value)).toBe(points);
    expect(downsampleLttb(points, 2, (value) => value)).toBe(points);
  });

  test('保留首尾，并把中间尖峰留在结果里', () => {
    const points = Array.from({ length: 101 }, (_, index) =>
      index === 50 ? 100 : 1,
    );
    const sampled = downsampleLttb(points, 11, (value) => value);

    expect(sampled).toHaveLength(11);
    expect(sampled[0]).toBe(1);
    expect(sampled[sampled.length - 1]).toBe(1);
    expect(sampled).toContain(100);
  });
});
