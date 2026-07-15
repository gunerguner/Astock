import type {
  ImportAllResult,
  ImportProgressEvent,
  ImportStreamError,
} from '@/api/admin';

export type PhaseKey = 'turnover' | 'point' | 'stock' | 'global_assets';

export type PhaseStatus = 'pending' | 'running' | 'done' | 'failed';

export interface PhaseState {
  phase: PhaseKey;
  label: string;
  status: PhaseStatus;
  current: number;
  total: number;
  imported: number;
  detail?: string;
  elapsed?: number;
  source_errors?: Record<string, string | null> | null;
}

export type RefreshOverallStatus = 'idle' | 'running' | 'done' | 'error';

export interface RefreshProgressState {
  phases: Record<PhaseKey, PhaseState>;
  completedCount: number;
  totalPhases: number;
  overallStatus: RefreshOverallStatus;
  finalResult: ImportAllResult | null;
  errorMessage: string | null;
  errorPhase: PhaseKey | null;
}

export const PHASE_ORDER: PhaseKey[] = [
  'turnover',
  'point',
  'stock',
  'global_assets',
];

export function createInitialProgressState(): RefreshProgressState {
  return {
    phases: {
      turnover: {
        phase: 'turnover',
        label: '',
        status: 'pending',
        current: 0,
        total: 1,
        imported: 0,
      },
      point: {
        phase: 'point',
        label: '',
        status: 'pending',
        current: 0,
        total: 1,
        imported: 0,
      },
      stock: {
        phase: 'stock',
        label: '',
        status: 'pending',
        current: 0,
        total: 0,
        imported: 0,
      },
      global_assets: {
        phase: 'global_assets',
        label: '',
        status: 'pending',
        current: 0,
        total: 1,
        imported: 0,
      },
    },
    completedCount: 0,
    totalPhases: PHASE_ORDER.length,
    overallStatus: 'idle',
    finalResult: null,
    errorMessage: null,
    errorPhase: null,
  };
}

function mapProgressStatus(status: ImportProgressEvent['status']): PhaseStatus {
  if (status === 'running') return 'running';
  if (status === 'done') return 'done';
  if (status === 'failed') return 'failed';
  return 'pending';
}

export function applyProgressEvent(
  state: RefreshProgressState,
  event: ImportProgressEvent,
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
    return item.status === 'done' || item.status === 'failed';
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
  error: ImportStreamError,
): RefreshProgressState {
  const errorPhase = (error.phase as PhaseKey | undefined) ?? null;
  const nextPhases = { ...state.phases };
  if (errorPhase && nextPhases[errorPhase]) {
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
    errorPhase,
  };
}

export function applyStreamDone(
  state: RefreshProgressState,
  result: ImportAllResult,
): RefreshProgressState {
  const nextPhases = { ...state.phases };
  PHASE_ORDER.forEach((key) => {
    const item = result[key];
    if (!item) return;
    nextPhases[key] = {
      ...nextPhases[key],
      status: item.status === 'failed' ? 'failed' : 'done',
      imported: item.imported,
      total: item.total,
      elapsed: item.elapsed,
      source_errors: item.source_errors,
    };
  });

  return {
    ...state,
    phases: nextPhases,
    completedCount: PHASE_ORDER.length,
    overallStatus: 'done',
    finalResult: result,
    errorMessage: null,
    errorPhase: null,
  };
}
