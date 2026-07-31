import { streamPost } from '@/utils/sse-stream';
import request from './request';

const STREAM_URL = '/api/v1/admin/data/import/stream';

/** 与 nginx proxy_read_timeout / GUNICORN_TIMEOUT 对齐，避免长任务被前端误判为断连 */
const IMPORT_STREAM_IDLE_TIMEOUT_MS = 300_000;

/** SSE 流式全量数据导入 POST /admin/data/import/stream */
export function refreshAllDataStream(
  handlers: API.ImportStreamHandlers,
): AbortController {
  return streamPost<
    API.ImportProgressEvent,
    API.ImportAllResult,
    API.ImportStreamError
  >(STREAM_URL, handlers, {
    idleTimeoutMs: IMPORT_STREAM_IDLE_TIMEOUT_MS,
  });
}

/** 获取同步状态 GET /admin/data/sync-status */
export function fetchSyncStatusApi(): Promise<API.SyncStatus> {
  return request.get('/admin/data/sync-status');
}
