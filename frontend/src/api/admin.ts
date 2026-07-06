import axios from 'axios';

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
  status: ImportStatus;
}

export function refreshAllDataApi() {
  return axios.post<ImportAllResult>('/admin/data/import', null, {
    timeout: REFRESH_TIMEOUT,
  });
}
