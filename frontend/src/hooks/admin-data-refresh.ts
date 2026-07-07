import { ref } from 'vue';
import { Notification } from '@arco-design/web-vue';
import {
  refreshAllDataApi,
  type ImportAllResult,
  type ImportResultItem,
} from '@/api/admin';

const DATASET_LABELS: Record<keyof Omit<ImportAllResult, 'status'>, string> = {
  turnover: '成交额',
  point: '上证点位',
  stock: '个股切片',
  global_assets: '全球资产',
};

function collectSourceNotes(result: ImportAllResult): string[] {
  const lines: string[] = [];
  (Object.keys(DATASET_LABELS) as Array<keyof typeof DATASET_LABELS>).forEach(
    (key) => {
      const item = result[key] as ImportResultItem | undefined;
      if (!item?.source_errors) return;
      Object.entries(item.source_errors).forEach(([source, message]) => {
        if (message) {
          lines.push(`${DATASET_LABELS[key]}(${source}): ${message}`);
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
          title: '数据刷新失败',
          content: content ?? '',
          duration: 8000,
        });
        return;
      }

      if (result.status === 'partial_failure') {
        Notification.warning({
          title: '数据部分刷新成功',
          content: content ?? '',
          duration: 8000,
        });
        return;
      }

      Notification.success({
        title: '数据刷新成功',
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
