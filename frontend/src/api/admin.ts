import { streamPost } from '@/utils/sse-stream';
import request from './request';

export type ImportStatus = 'failed' | 'partial_failure' | 'success';

export interface ImportResultItem {
  imported: number;
  total: number;
  last_date: string | null;
  last_synced_at: string | null;
  status: ImportStatus;
  source_errors: Record<string, string | null> | null;
  elapsed?: number;
}

export interface ImportAllResult {
  turnover: ImportResultItem;
  point: ImportResultItem;
  stock: ImportResultItem;
  global_assets?: ImportResultItem;
  status: ImportStatus;
}

export type ImportPhaseKey = 'turnover' | 'point' | 'stock' | 'global_assets';

export interface ImportProgressEvent {
  phase: ImportPhaseKey;
  label: string;
  status: 'running' | 'done' | 'failed';
  current: number;
  total: number;
  imported: number;
  detail?: string;
  elapsed?: number;
  source_errors?: Record<string, string | null> | null;
}

export interface ImportStreamError {
  message: string;
  phase?: ImportPhaseKey;
}

export interface ImportStreamHandlers {
  onProgress?: (event: ImportProgressEvent) => void;
  onDone?: (result: ImportAllResult) => void;
  onError?: (error: ImportStreamError | { message: string }) => void;
}

const STREAM_URL = '/api/v1/admin/data/import/stream';

/** 与 nginx proxy_read_timeout / GUNICORN_TIMEOUT 对齐，避免长任务被前端误判为断连 */
const IMPORT_STREAM_IDLE_TIMEOUT_MS = 300_000;

export function refreshAllDataStream(
  handlers: ImportStreamHandlers,
): AbortController {
  return streamPost<ImportProgressEvent, ImportAllResult, ImportStreamError>(
    STREAM_URL,
    handlers,
    { idleTimeoutMs: IMPORT_STREAM_IDLE_TIMEOUT_MS },
  );
}

export interface SyncStatusItem {
  last_synced_date: string | null;
  last_synced_at: string | null;
  status: ImportStatus | null;
}

export interface SyncStatus {
  turnover: SyncStatusItem;
  point: SyncStatusItem;
  stock: SyncStatusItem;
  global_assets: SyncStatusItem;
}

export function fetchSyncStatusApi(): Promise<SyncStatus> {
  return request.get('/admin/data/sync-status');
}
