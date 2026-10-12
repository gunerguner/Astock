import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';

import { streamPost } from '@/utils/sse-stream';

const encoder = new TextEncoder();

/** 用 ReadableStream 构造 SSE 响应,支持分片(粘包/半帧) */
function sseResponse(
  chunks: string[],
  init?: {
    ok?: boolean;
    status?: number;
    body?: ReadableStream<Uint8Array> | null;
  },
) {
  const { ok = true, status = 200, body = null } = init ?? {};
  const stream =
    body ??
    new ReadableStream<Uint8Array>({
      start(controller) {
        chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
        controller.close();
      },
    });
  return {
    ok,
    status,
    json: async () => {
      throw new Error('no json');
    },
    body: stream,
  };
}

function flush() {
  return new Promise<void>((resolve) => {
    setTimeout(resolve, 0);
  });
}

describe('streamPost(SSE POST 解析)', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => sseResponse([])),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test('progress/done 事件分发,JSON 自动解析', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        sseResponse([
          'event: progress\ndata: {"current":1,"total":3}\n\nevent: done\ndata: {"imported":3}\n\n',
        ]),
      ),
    );
    const onProgress = vi.fn();
    const onDone = vi.fn();
    streamPost('/stream', { onProgress, onDone });
    await flush();
    expect(onProgress).toHaveBeenCalledWith({ current: 1, total: 3 });
    expect(onDone).toHaveBeenCalledWith({ imported: 3 });
  });

  test('跨 chunk 粘包与半帧正确拼接', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        sseResponse([
          'event: progress\nda',
          'ta: {"current":2}\n\nevent: done\ndata: {}\n\n',
        ]),
      ),
    );
    const onProgress = vi.fn();
    const onDone = vi.fn();
    streamPost('/stream', { onProgress, onDone });
    await flush();
    expect(onProgress).toHaveBeenCalledWith({ current: 2 });
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  test('非 JSON payload 原样透传', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => sseResponse(['event: error\ndata: 后端维护中\n\n'])),
    );
    const onError = vi.fn();
    streamPost('/stream', { onError });
    await flush();
    expect(onError).toHaveBeenCalledWith('后端维护中');
  });

  test('data 缺失的帧(如 ping)被忽略且不断流', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        sseResponse(['event: ping\n\nevent: done\ndata: {"ok":1}\n\n']),
      ),
    );
    const onDone = vi.fn();
    const onError = vi.fn();
    streamPost('/stream', { onDone, onError });
    await flush();
    expect(onDone).toHaveBeenCalledWith({ ok: 1 });
    expect(onError).not.toHaveBeenCalled();
  });

  test('HTTP 非 2xx 用响应体 message 报错', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        sseResponse([], {
          ok: false,
          status: 502,
          body: new ReadableStream<Uint8Array>(),
        }),
      ),
    );
    // 单独覆盖 json 行为
    const fetchMock = vi.fn(async () => ({
      ok: false,
      status: 502,
      json: async () => ({ message: '上游失败' }),
      body: null,
    }));
    vi.stubGlobal('fetch', fetchMock);
    const onError = vi.fn();
    streamPost('/stream', { onError });
    await flush();
    expect(onError).toHaveBeenCalledWith({ message: '上游失败' });
  });

  test('HTTP 非 2xx 且无 JSON 时回退状态码文案', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: false,
        status: 500,
        json: async () => {
          throw new Error('bad');
        },
        body: null,
      })),
    );
    const onError = vi.fn();
    streamPost('/stream', { onError });
    await flush();
    expect(onError).toHaveBeenCalledWith({ message: '请求失败 (500)' });
  });

  test('流关闭但无终态事件 → 连接意外断开', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => sseResponse(['event: progress\ndata: {}\n\n'])),
    );
    const onError = vi.fn();
    const onDone = vi.fn();
    streamPost('/stream', { onError, onDone });
    await flush();
    expect(onError).toHaveBeenCalledWith({ message: '连接意外断开' });
    expect(onDone).not.toHaveBeenCalled();
  });

  test('fetch 网络异常 → 透传错误消息', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('network down');
      }),
    );
    const onError = vi.fn();
    streamPost('/stream', { onError });
    await flush();
    expect(onError).toHaveBeenCalledWith({ message: 'network down' });
  });

  test('idle 超时中止并报连接超时', async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      'fetch',
      vi.fn(
        () =>
          new Promise(() => {
            /* 永不 resolve */
          }),
      ),
    );
    const onError = vi.fn();
    streamPost('/stream', { onError }, { idleTimeoutMs: 1000 });
    await vi.advanceTimersByTimeAsync(1100);
    expect(onError).toHaveBeenCalledWith({ message: '连接超时' });
    vi.useRealTimers();
  });
});
