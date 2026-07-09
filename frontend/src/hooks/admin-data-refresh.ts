import { ref } from 'vue';
import {
  refreshAllDataStream,
  type ImportAllResult,
  type ImportProgressEvent,
  type ImportStreamError,
} from '@/api/admin';
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

export default function useAdminDataRefresh() {
  function resetProgressState() {
    progressState.value = initProgressState();
  }

  function refreshAllData() {
    if (refreshing.value) return;

    abortController?.abort();
    resetProgressState();
    refreshing.value = true;
    progressVisible.value = true;
    progressState.value.overallStatus = 'running';

    abortController = refreshAllDataStream({
      onProgress: (event: ImportProgressEvent) => {
        progressState.value = applyProgressEvent(progressState.value, event);
      },
      onDone: (result: ImportAllResult) => {
        progressState.value = applyStreamDone(progressState.value, result);
        refreshing.value = false;
        abortController = null;
      },
      onError: (error: ImportStreamError) => {
        progressState.value = applyStreamError(progressState.value, error);
        refreshing.value = false;
        abortController = null;
      },
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
