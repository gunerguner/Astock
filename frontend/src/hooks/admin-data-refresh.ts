import { ref } from 'vue';
import { Notification } from '@arco-design/web-vue';
import {
  refreshAllDataApi,
  type ImportAllResult,
  type ImportResultItem,
} from '@/api/admin';
import i18n from '@/locale';

const { t } = i18n.global;

function getDatasetLabels(): Record<
  keyof Omit<ImportAllResult, 'status'>,
  string
> {
  return {
    turnover: t('adminRefresh.dataset.turnover'),
    point: t('adminRefresh.dataset.point'),
    stock: t('adminRefresh.dataset.stock'),
    global_assets: t('adminRefresh.dataset.globalAssets'),
  };
}

function collectSourceNotes(result: ImportAllResult): string[] {
  const lines: string[] = [];
  const datasetLabels = getDatasetLabels();
  (Object.keys(datasetLabels) as Array<keyof typeof datasetLabels>).forEach(
    (key) => {
      const item = result[key] as ImportResultItem | undefined;
      if (!item?.source_errors) return;
      Object.entries(item.source_errors).forEach(([source, message]) => {
        if (message) {
          lines.push(`${datasetLabels[key]}(${source}): ${message}`);
        }
      });
    }
  );
  return lines;
}

export default function useAdminDataRefresh() {
  const refreshing = ref(false);

  async function refreshAllData() {
    if (refreshing.value) return;
    refreshing.value = true;

    try {
      const result = await refreshAllDataApi();
      const detailLines = collectSourceNotes(result);
      const content =
        detailLines.length > 0 ? detailLines.join('\n') : undefined;

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
    } catch {
      // 请求错误已由 axios 拦截器统一提示
    } finally {
      refreshing.value = false;
    }
  }

  return { refreshAllData, refreshing };
}
