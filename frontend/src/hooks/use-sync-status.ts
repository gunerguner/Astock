import { computed, ref } from 'vue';
import {
  fetchSyncStatusApi,
  type SyncStatus,
  type SyncStatusItem
} from '@/api/admin';
import formatSyncMeta from '@/utils/sync-meta';

export default function useSyncStatus(
  ...metaKeys: Array<keyof SyncStatus | undefined>
) {
  const syncStatus = ref<SyncStatus | null>(null);

  const loadSyncStatus = async () => {
    try {
      syncStatus.value = await fetchSyncStatusApi();
    } catch {
      // 静默失败，不影响主要数据展示
    }
  };

  const metaText = computed(() => {
    if (metaKeys.length === 0) {
      return '';
    }
    const items = metaKeys.map((key) =>
      key ? syncStatus.value?.[key] : undefined
    ) as Array<SyncStatusItem | undefined | null>;
    return formatSyncMeta(...items);
  });

  const panelMetaText = (key: keyof SyncStatus) =>
    formatSyncMeta(syncStatus.value?.[key]);

  return {
    syncStatus,
    loadSyncStatus,
    metaText,
    panelMetaText
  };
}
