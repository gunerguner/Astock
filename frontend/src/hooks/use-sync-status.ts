import { computed, ref } from 'vue';
import { fetchSyncStatusApi } from '@/api/admin';
import formatSyncMeta from '@/utils/sync-meta';

export default function useSyncStatus(
  ...metaKeys: Array<keyof API.SyncStatus | undefined>
) {
  const syncStatus = ref<API.SyncStatus | null>(null);

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
    const items: Array<API.SyncStatusItem | undefined> = metaKeys.map((key) =>
      key ? syncStatus.value?.[key] : undefined,
    );
    return formatSyncMeta(...items);
  });

  const panelMetaText = (key: keyof API.SyncStatus) =>
    formatSyncMeta(syncStatus.value?.[key]);

  return {
    syncStatus,
    loadSyncStatus,
    metaText,
    panelMetaText,
  };
}
