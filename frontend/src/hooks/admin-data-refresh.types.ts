export type PhaseKey = API.ImportPhaseKey;

export type PhaseStatus =
  'pending' | 'running' | 'done' | 'failed' | 'partial_failure';

export interface PhaseState {
  phase: PhaseKey;
  label: string;
  status: PhaseStatus;
  current: number;
  total: number;
  imported: number;
  detail?: string;
  elapsed?: number;
  source_errors?: Record<string, string>;
}

export type RefreshOverallStatus =
  'idle' | 'running' | 'done' | 'partial' | 'error';

export interface RefreshProgressState {
  phases: Record<PhaseKey, PhaseState>;
  completedCount: number;
  totalPhases: number;
  overallStatus: RefreshOverallStatus;
  errorMessage: string | null;
}

export const PHASE_ORDER: PhaseKey[] = [
  'turnover',
  'point',
  'stock',
  'global_assets',
  'us_macro',
  'cn_macro',
  'market_overview',
];

export function isPhaseKey(value: string | undefined): value is PhaseKey {
  return (
    value === 'turnover' ||
    value === 'point' ||
    value === 'stock' ||
    value === 'global_assets' ||
    value === 'us_macro' ||
    value === 'cn_macro' ||
    value === 'market_overview'
  );
}

export function createInitialProgressState(): RefreshProgressState {
  const phases = Object.fromEntries(
    PHASE_ORDER.map((phase) => [
      phase,
      {
        phase,
        label: '',
        status: 'pending' as const,
        current: 0,
        total: phase === 'stock' ? 0 : 1,
        imported: 0,
      },
    ]),
  ) as Record<PhaseKey, PhaseState>;

  return {
    phases,
    completedCount: 0,
    totalPhases: PHASE_ORDER.length,
    overallStatus: 'idle',
    errorMessage: null,
  };
}

function mapProgressStatus(
  status: API.ImportProgressEvent['status'],
): PhaseStatus {
  if (status === 'running') return 'running';
  if (status === 'done') return 'done';
  if (status === 'failed') return 'failed';
  if (status === 'partial_failure') return 'partial_failure';
  return 'pending';
}

function mapResultStatus(status: API.ImportStatus): PhaseStatus {
  if (status === 'failed') return 'failed';
  if (status === 'partial_failure') return 'partial_failure';
  return 'done';
}

export function applyProgressEvent(
  state: RefreshProgressState,
  event: API.ImportProgressEvent,
): RefreshProgressState {
  const { phase } = event;
  const nextPhases = { ...state.phases };
  const prev = nextPhases[phase];
  const nextStatus = mapProgressStatus(event.status);

  nextPhases[phase] = {
    ...prev,
    phase,
    label: event.label || prev.label,
    status: nextStatus,
    current: event.current ?? prev.current,
    total: event.total ?? prev.total,
    imported: event.imported ?? prev.imported,
    detail: event.detail ?? prev.detail,
    elapsed: event.elapsed ?? prev.elapsed,
    source_errors: event.source_errors ?? prev.source_errors,
  };

  const completedCount = PHASE_ORDER.filter((key) => {
    const item = nextPhases[key];
    return (
      item.status === 'done' ||
      item.status === 'failed' ||
      item.status === 'partial_failure'
    );
  }).length;

  return {
    ...state,
    phases: nextPhases,
    completedCount,
    overallStatus: 'running',
  };
}

export function applyStreamError(
  state: RefreshProgressState,
  error: API.ImportStreamError,
): RefreshProgressState {
  const errorPhase = isPhaseKey(error.phase) ? error.phase : null;
  const nextPhases = { ...state.phases };
  if (errorPhase) {
    nextPhases[errorPhase] = {
      ...nextPhases[errorPhase],
      status: 'failed',
    };
  }

  return {
    ...state,
    phases: nextPhases,
    overallStatus: 'error',
    errorMessage: error.message,
  };
}

export function applyStreamDone(
  state: RefreshProgressState,
  result: API.ImportAllResult,
): RefreshProgressState {
  const nextPhases = { ...state.phases };
  PHASE_ORDER.forEach((key) => {
    const item = result[key];
    if (!item) return;
    nextPhases[key] = {
      ...nextPhases[key],
      status: mapResultStatus(item.status),
      imported: item.imported,
      total: item.total,
      elapsed: item.elapsed,
      source_errors: item.source_errors,
    };
  });

  const statuses = PHASE_ORDER.map((key) => nextPhases[key].status);
  let overallStatus: RefreshProgressState['overallStatus'] = 'done';
  if (statuses.some((item) => item === 'failed')) {
    overallStatus = 'error';
  } else if (statuses.some((item) => item === 'partial_failure')) {
    overallStatus = 'partial';
  }

  return {
    ...state,
    phases: nextPhases,
    completedCount: PHASE_ORDER.length,
    overallStatus,
    errorMessage: null,
  };
}
