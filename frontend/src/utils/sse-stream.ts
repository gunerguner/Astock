import i18n from '@/locale';

const { t } = i18n.global;

export interface SSEHandlers<
  TProgress = unknown,
  TDone = unknown,
  TError extends { message: string } = { message: string },
> {
  onProgress?: (data: TProgress) => void;
  onDone?: (data: TDone) => void;
  /** 服务端 error 事件为 TError；本地断连/超时等仅保证有 message。HTTP 失败附带 status */
  onError?: (data: TError | { message: string; status?: number }) => void;
}

export interface StreamPostOptions {
  idleTimeoutMs?: number;
  headers?: Record<string, string>;
}

function parseSSEFrame(raw: string): { event: string; data: string } | null {
  const lines = raw.split('\n');
  let event = 'message';
  const dataLines: string[] = [];

  lines.forEach((line) => {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim();
      return;
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim());
    }
  });

  if (dataLines.length === 0) {
    return null;
  }

  return { event, data: dataLines.join('\n') };
}

export function streamPost<
  TProgress = unknown,
  TDone = unknown,
  TError extends { message: string } = { message: string },
>(
  url: string,
  handlers: SSEHandlers<TProgress, TDone, TError>,
  options: StreamPostOptions = {},
): AbortController {
  const controller = new AbortController();
  const idleTimeoutMs = options.idleTimeoutMs ?? 30_000;

  let idleTimer: ReturnType<typeof setTimeout> | null = null;

  const emitLocalError = (message: string) => {
    handlers.onError?.({ message });
  };

  const resetIdleTimer = () => {
    if (idleTimer) {
      clearTimeout(idleTimer);
    }
    idleTimer = setTimeout(() => {
      controller.abort();
      emitLocalError(t('sse.timeout'));
    }, idleTimeoutMs);
  };

  const clearIdleTimer = () => {
    if (idleTimer) {
      clearTimeout(idleTimer);
      idleTimer = null;
    }
  };

  const run = async () => {
    resetIdleTimer();
    let receivedTerminalEvent = false;

    const dispatchFrame = (event: string, payload: string) => {
      resetIdleTimer();
      let parsed: unknown = payload;
      if (payload) {
        try {
          parsed = JSON.parse(payload);
        } catch {
          parsed = payload;
        }
      }

      switch (event) {
        case 'progress':
          handlers.onProgress?.(parsed as TProgress);
          break;
        case 'done':
          receivedTerminalEvent = true;
          handlers.onDone?.(parsed as TDone);
          break;
        case 'error':
          receivedTerminalEvent = true;
          handlers.onError?.(parsed as TError);
          break;
        default:
          // ping 等事件仅重置 idle（已在上方 resetIdleTimer）
          break;
      }
    };

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          Accept: 'text/event-stream',
          ...options.headers,
        },
        signal: controller.signal,
      });

      if (!response.ok) {
        let message = t('sse.httpFailed', { status: response.status });
        try {
          const body = await response.json();
          message = body.message || message;
        } catch {
          // ignore parse error
        }
        receivedTerminalEvent = true;
        handlers.onError?.({ message, status: response.status });
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        receivedTerminalEvent = true;
        emitLocalError(t('sse.noBody'));
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';
      let streamDone = false;

      while (!streamDone) {
        // eslint-disable-next-line no-await-in-loop
        const { done, value } = await reader.read();
        streamDone = done;
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split('\n\n');
        buffer = frames.pop() ?? '';

        frames.forEach((frame) => {
          const trimmed = frame.trim();
          if (!trimmed) return;
          const parsed = parseSSEFrame(trimmed);
          if (!parsed) return;
          dispatchFrame(parsed.event, parsed.data);
        });
      }

      const tail = buffer.trim();
      if (tail) {
        const parsed = parseSSEFrame(tail);
        if (parsed) {
          dispatchFrame(parsed.event, parsed.data);
        }
      }

      if (!receivedTerminalEvent) {
        emitLocalError(t('sse.disconnected'));
      }
    } catch (error) {
      if (controller.signal.aborted) {
        return;
      }
      const message =
        error instanceof Error ? error.message : t('sse.networkFailed');
      emitLocalError(message);
    } finally {
      clearIdleTimer();
    }
  };

  run().catch(() => {
    // run() 内部已处理错误回调
  });

  return controller;
}
