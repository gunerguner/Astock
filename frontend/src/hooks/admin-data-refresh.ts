import { ref } from 'vue';
import { Notification } from '@arco-design/web-vue';
import {
  refreshAllDataStream,
  type ImportAllResult,
  type ImportProgressEvent,
  type ImportResultItem,
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

function collectSourceNotes(result: ImportAllResult): string[] {
  const lines: string[] = [];
  const datasetLabels = getDatasetLabels();
  PHASE_ORDER.forEach((key) => {
    const item = result[key] as ImportResultItem | undefined;
    if (!item?.source_errors) return;
    Object.entries(item.source_errors).forEach(([source, message]) => {
      if (message) {
        lines.push(`${datasetLabels[key]}(${source}): ${message}`);
      }
    });
  });
  return lines;
}

function notifyResult(result: ImportAllResult) {
  const detailLines = collectSourceNotes(result);
  const content = detailLines.length > 0 ? detailLines.join('\n') : undefined;

  if (result.status === 'failed') {
    Notification.error({
      title: t('adminRefresh.notification.failedTitle'),
      content: content ?? '',
      duration: 8000,
    });
    return;
  }

  if (result.status === 'partial_failure') {
    Notification.warning({
      title: t('adminRefresh.notification.partialTitle'),
      content: content ?? '',
      duration: 8000,
    });
    return;
  }

  Notification.success({
    title: t('adminRefresh.notification.successTitle'),
    content: '',
    duration: 3000,
  });
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
        notifyResult(result);
        refreshing.value = false;
        abortController = null;
      },
      onError: (error: ImportStreamError) => {
        progressState.value = applyStreamError(progressState.value, error);
        Notification.error({
          title: t('adminRefresh.notification.failedTitle'),
          content: error.message,
          duration: 8000,
        });
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
