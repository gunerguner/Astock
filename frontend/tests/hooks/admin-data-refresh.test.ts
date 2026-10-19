import { describe, expect, it } from 'vitest';

import {
  applyStreamDone,
  createInitialProgressState,
} from '@/hooks/admin-data-refresh.types';

function item(status: API.ImportStatus): API.ImportResultItem {
  return {
    imported: 1,
    total: 1,
    last_date: '2026-01-06',
    last_synced_at: null,
    status,
    source_errors: status === 'success' ? {} : { turnover: '缺一天' },
    elapsed: 0.1,
  };
}

describe('applyStreamDone', () => {
  it('maps partial_failure to a partial overall status', () => {
    const state = createInitialProgressState();
    const next = applyStreamDone(state, {
      turnover: item('partial_failure'),
      point: item('success'),
      stock: item('success'),
      status: 'partial_failure',
    });
    expect(next.phases.turnover.status).toBe('partial_failure');
    expect(next.overallStatus).toBe('partial');
    expect(next.phases.turnover.source_errors).toEqual({ turnover: '缺一天' });
  });
});
