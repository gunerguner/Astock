import { describe, expect, test } from 'vitest';
import describeError from '@/utils/error-message';

describe('describeError', () => {
  test('prefers the API message over the transport error', () => {
    const error = Object.assign(
      new Error('Request failed with status code 500'),
      {
        response: { data: { message: '服务暂不可用' } },
      },
    );
    expect(describeError(error, '加载失败')).toBe('服务暂不可用');
  });

  test('uses the error message, then the fallback', () => {
    expect(describeError(new Error('网络请求失败'), '加载失败')).toBe(
      '网络请求失败',
    );
    expect(describeError(new Error('Network Error'), '加载失败')).toBe(
      '加载失败',
    );
    expect(describeError(null, '加载失败')).toBe('加载失败');
  });
});
