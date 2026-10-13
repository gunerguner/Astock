import { ref } from 'vue';
import { refreshAllDataStream } from '@/api/admin';
import i18n from '@/locale';
import { emitDataRefresh } from '@/utils/data-refresh';
import {
  applyProgressEvent,
  applyStreamDone,
  applyStreamError,
  createInitialProgressState,
  PHASE_ORDER,
  type PhaseKey,
  type RefreshProgressState,
} from '@/hooks/admin-data-refresh.types';

const { t } = i18n.global;

const refreshing = ref(false);
const progressVisible = ref(false);
const progressState = ref<RefreshProgressState>(createInitialProgressState());

let abortController: AbortController | null = null;

function getDatasetLabels(): Record<PhaseKey, string> {
  return {
    turnover: t('adminRefresh.dataset.turnover'),
    point: t('adminRefresh.dataset.point'),
    stock: t('adminRefresh.dataset.stock'),
    global_assets: t('adminRefresh.dataset.globalAssets'),
    us_macro: t('adminRefresh.dataset.usMacro'),
    cn_macro: t('adminRefresh.dataset.cnMacro'),
    market_overview: t('adminRefresh.dataset.marketOverview'),
  };
}

function initProgressState(): RefreshProgressState {
  const labels = getDatasetLabels();
  const state = createInitialProgressState();
  PHASE_ORDER.forEach((key) => {
    state.phases[key].label = labels[key];
  });
  return state;
}

export type RefreshStartResult =
  { accepted: true } | { accepted: false; message: string };

function isAuthRejection(error: { status?: number }): boolean {
  return error.status === 401 || error.status === 503;
}

export default function useAdminDataRefresh() {
  function resetProgressState() {
    progressState.value = initProgressState();
  }

  function refreshAllData(password: string): Promise<RefreshStartResult> {
    if (refreshing.value) {
      return Promise.resolve({ accepted: false, message: '' });
    }

    return new Promise((resolve) => {
      let accepted = false;
      const accept = () => {
        if (accepted) return;
        accepted = true;
        progressVisible.value = true;
        progressState.value.overallStatus = 'running';
        resolve({ accepted: true });
      };

      abortController?.abort();
      resetProgressState();
      refreshing.value = true;

      abortController = refreshAllDataStream(
        {
          onProgress: (event: API.ImportProgressEvent) => {
            accept();
            progressState.value = applyProgressEvent(
              progressState.value,
              event,
            );
          },
          onDone: (result: API.ImportAllResult) => {
            accept();
            progressState.value = applyStreamDone(progressState.value, result);
            refreshing.value = false;
            abortController = null;
          },
          onError: (error: API.ImportStreamError) => {
            if (!accepted && isAuthRejection(error)) {
              refreshing.value = false;
              abortController = null;
              resetProgressState();
              resolve({ accepted: false, message: error.message });
              return;
            }
            accept();
            progressState.value = applyStreamError(progressState.value, error);
            refreshing.value = false;
            abortController = null;
          },
        },
        password,
      );
    });
  }

  function closeProgressModal() {
    if (refreshing.value) return;
    progressVisible.value = false;
    if (progressState.value.overallStatus === 'done') {
      emitDataRefresh();
    }
    resetProgressState();
  }

  return {
    refreshing,
    progressVisible,
    progressState,
    refreshAllData,
    closeProgressModal,
  };
}
