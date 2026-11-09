import { describe, expect, it } from 'vitest';

import {
  applyProgressEvent,
  applyStreamDone,
  createInitialProgressState,
  tickPhaseElapsed,
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

describe('tickPhaseElapsed', () => {
  it('进行中阶段按本地时钟计秒，结束后不再改写', () => {
    const started = applyProgressEvent(createInitialProgressState(), {
      phase: 'market_overview',
      label: '市场概览',
      status: 'running',
      current: 0,
      total: 1,
      imported: 0,
      elapsed: 0,
    });
    expect(started.activePhaseStartedAt).not.toBeNull();

    const ticking = tickPhaseElapsed(
      started,
      (started.activePhaseStartedAt as number) + 2500,
    );
    expect(ticking.phases.market_overview.elapsed).toBe(2.5);

    const done = applyProgressEvent(ticking, {
      phase: 'market_overview',
      label: '市场概览',
      status: 'done',
      current: 1,
      total: 1,
      imported: 10,
      elapsed: 4.2,
    });
    expect(done.activePhaseStartedAt).toBeNull();
    expect(tickPhaseElapsed(done, Date.now())).toBe(done);
  });
});
