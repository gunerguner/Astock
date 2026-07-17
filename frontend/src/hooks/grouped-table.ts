import type { TableColumnData, TableData } from '@arco-design/web-vue';
import type { MaybeRef } from 'vue';
import { computed, unref } from 'vue';

export interface BaseDividerRow {
  key: string;
  rowKind: 'divider';
  label: string;
}

export function isDividerRow(record: unknown): record is BaseDividerRow {
  if (typeof record !== 'object' || record === null || !('rowKind' in record)) {
    return false;
  }
  return (record as Record<string, unknown>).rowKind === 'divider';
}

export function toTableRow<T>(record: TableData): T {
  return record as T;
}

export function useDividerTable(columns: MaybeRef<TableColumnData[]>) {
  const columnCount = computed(() => unref(columns).length);

  const spanMethod = ({
    record,
    columnIndex,
  }: {
    record: TableData;
    columnIndex: number;
  }) => {
    if (isDividerRow(record)) {
      if (columnIndex === 0) {
        return { rowspan: 1, colspan: columnCount.value };
      }
      return { rowspan: 0, colspan: 0 };
    }
    return { rowspan: 1, colspan: 1 };
  };

  const rowClass = (record: TableData) =>
    isDividerRow(record) ? 'section-divider-row' : '';

  return { spanMethod, rowClass };
}
