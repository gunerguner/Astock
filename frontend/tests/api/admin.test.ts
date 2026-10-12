import { beforeEach, describe, expect, test, vi } from 'vitest';

import { fetchSyncStatusApi, refreshAllDataStream } from '@/api/admin';

const { getMock, streamPostMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  streamPostMock: vi.fn(() => ({ abort: vi.fn() })),
}));

vi.mock('@/api/request', () => ({ default: { get: getMock, post: vi.fn() } }));
vi.mock('@/utils/sse-stream', () => ({ streamPost: streamPostMock }));

beforeEach(() => {
  getMock.mockReset();
  streamPostMock.mockClear();
  getMock.mockResolvedValue(null);
});

describe('admin 数据接口', () => {
  test('sync-status:GET /admin/data/sync-status', async () => {
    await fetchSyncStatusApi();
    expect(getMock).toHaveBeenCalledWith('/admin/data/sync-status');
  });

  test('全量刷新走 SSE POST,空闲超时 300s(与 nginx/Gunicorn 对齐)', () => {
    const handlers = { onProgress: vi.fn(), onDone: vi.fn(), onError: vi.fn() };
    refreshAllDataStream(handlers);

    expect(streamPostMock).toHaveBeenCalledTimes(1);
    const [url, passedHandlers, options] = streamPostMock.mock.calls[0];
    expect(url).toBe('/api/v1/admin/data/import/stream');
    expect(passedHandlers).toBe(handlers);
    expect(options).toEqual({ idleTimeoutMs: 300_000 });
  });
});
