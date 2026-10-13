import { beforeEach, describe, expect, test, vi } from 'vitest';

import request from '@/api/request';

const { messageMock, interceptors, instanceLike } = vi.hoisted(() => {
  const captured = {
    request: { ok: undefined as unknown, err: undefined as unknown },
    response: {
      ok: undefined as unknown as (response: unknown) => unknown,
      err: undefined as unknown,
    },
  };
  return {
    interceptors: captured,
    messageMock: { error: vi.fn() },
    instanceLike: {
      interceptors: {
        request: {
          use: (ok: unknown, err: unknown) => {
            captured.request = { ok, err };
          },
        },
        response: {
          use: (ok: (response: unknown) => unknown, err: unknown) => {
            captured.response = { ok, err };
          },
        },
      },
      get: vi.fn(),
      post: vi.fn(),
    },
  };
});

vi.mock('axios', () => ({ default: { create: vi.fn(() => instanceLike) } }));
vi.mock('@/locale', () => ({
  default: { global: { t: (key: string) => key } },
}));
vi.mock('@arco-design/web-vue', () => ({ Message: messageMock }));

describe('request 响应拦截器(信封解包)', () => {
  beforeEach(() => {
    messageMock.error.mockClear();
    instanceLike.get.mockClear();
  });

  test('code=0 直接解包为业务 data', () => {
    const payload = { code: 0, message: 'success', data: { top: 1 } };
    const result = interceptors.response.ok({ data: payload });
    expect(result).toEqual({ top: 1 });
    expect(messageMock.error).not.toHaveBeenCalled();
  });

  test('code≠0 弹错并 reject(Error message=信封 message)', async () => {
    const payload = { code: 1001, message: '参数校验失败', data: null };
    await expect(
      Promise.resolve().then(() => interceptors.response.ok({ data: payload })),
    ).rejects.toThrow('参数校验失败');
    expect(messageMock.error).toHaveBeenCalledTimes(1);
    expect(messageMock.error).toHaveBeenCalledWith(
      expect.objectContaining({ content: '参数校验失败' }),
    );
  });

  test('业务 data 可为 null(信封允许)', () => {
    const result = interceptors.response.ok({
      data: { code: 0, message: 'success', data: null },
    });
    expect(result).toBeNull();
  });

  test('HTTP 层错误优先取响应体 message', async () => {
    const error = {
      response: { data: { message: '上游失败' } },
      message: 'Request failed',
    };
    const reject = interceptors.response.err as (e: unknown) => Promise<never>;
    await expect(reject(error)).rejects.toBe(error);
    expect(messageMock.error).toHaveBeenCalledWith(
      expect.objectContaining({ content: '上游失败' }),
    );
  });
});

describe('request 实例封装', () => {
  test('get/post 透传到 axios 实例', () => {
    instanceLike.get.mockResolvedValueOnce({ ok: true });
    request.get('/x', { params: { a: 1 } });
    expect(instanceLike.get).toHaveBeenCalledWith('/x', { params: { a: 1 } });

    request.post('/y', { b: 2 });
    expect(instanceLike.post).toHaveBeenCalledWith('/y', { b: 2 }, undefined);
  });
});
