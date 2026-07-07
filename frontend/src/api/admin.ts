import request from './request';

const REFRESH_TIMEOUT = 5 * 60 * 1000;

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

export function refreshAllDataApi(): Promise<ImportAllResult> {
  return request.post('/admin/data/import', null, {
    timeout: REFRESH_TIMEOUT,
  });
}

export function refreshGlobalAssetsApi(): Promise<ImportResultItem> {
  return request.post('/admin/data/import', null, {
    params: { dataset: 'global_assets' },
    timeout: REFRESH_TIMEOUT,
  });
}

export interface SyncStatusItem {
  last_synced_date: string | null;
  last_synced_at: string | null;
  status: string | null;
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
