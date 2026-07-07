import type { SyncStatusItem } from '@/api/admin';
import i18n from '@/locale';

/**
 * 合并多个数据集的同步状态，取最新的数据日期，
 * 生成统一的"最新数据日期"展示文案。
 */
export default function formatSyncMeta(
  ...items: Array<SyncStatusItem | undefined | null>
): string {
  const validItems = items.filter((item): item is SyncStatusItem => !!item);
  if (validItems.length === 0) return '';

  const latestDate = validItems
    .map((item) => item.last_synced_date)
    .filter((d): d is string => !!d)
    .sort()
    .at(-1);

  return latestDate
    ? i18n.global.t('common.metaLatestDate', { date: latestDate })
    : '';
}
