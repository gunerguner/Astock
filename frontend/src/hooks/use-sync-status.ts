import { computed, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { fetchSyncStatusApi } from '@/api/admin';
import formatSyncMeta from '@/utils/sync-meta';

export default function useSyncStatus(
  ...metaKeys: Array<keyof API.SyncStatus | undefined>
) {
  const { t } = useI18n();
  const syncStatus = ref<API.SyncStatus | null>(null);
  const loadFailed = ref(false);

  const loadSyncStatus = async () => {
    try {
      syncStatus.value = await fetchSyncStatusApi();
      loadFailed.value = false;
    } catch {
      loadFailed.value = true;
      syncStatus.value = null;
    }
  };

  const metaText = computed(() => {
    if (loadFailed.value) {
      return t('common.loadFailed');
    }
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
