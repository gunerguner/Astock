import { h } from 'vue';
import { Tooltip } from '@arco-design/web-vue';
import type { TableColumnData } from '@arco-design/web-vue';
import type { ComposerTranslation } from 'vue-i18n';
import { formatAmount, formatPoint, numClass } from '@/utils/format';
import type { IndexConfig, MergedRow } from './use-bull-market';

const formatPeriodCompact = (start: string, end: string) => `${start}~${end}`;

const formatDays = (value: number | null, notAvailable = false) => {
  if (notAvailable) {
    return '—';
  }
  if (value === null) {
    return '-';
  }
  return String(value);
};

const renderUnavailableCell = (
  t: ComposerTranslation,
  content: string,
  notAvailable: boolean
) => {
  if (!notAvailable) {
    return h('span', { class: 'num' }, content);
  }
  return h(
    Tooltip,
    { content: t('pages.bullMarket.notAvailable') },
    {
      default: () => h('span', { class: 'num unavailable' }, content),
    }
  );
};

export default function buildMergedColumns(
  t: ComposerTranslation,
  indexConfigs: readonly IndexConfig[]
): TableColumnData[] {
  const indexColumns: TableColumnData[] = indexConfigs.map((index) => ({
    title: t(index.filterKey),
    children: [
      {
        title: t('pages.bullMarket.columns.standardDaysShort'),
        align: 'right',
        width: 56,
        render: ({ record }) => {
          const row = record as MergedRow;
          const cell = row.indices[index.code];
          return renderUnavailableCell(
            t,
            formatDays(cell?.days ?? null, cell?.notAvailable),
            cell?.notAvailable ?? false
          );
        },
      },
      {
        title: t('pages.bullMarket.columns.maxPointShort'),
        align: 'right',
        width: 76,
        render: ({ record }) => {
          const row = record as MergedRow;
          const cell = row.indices[index.code];
          const content = cell?.notAvailable
            ? '—'
            : formatPoint(cell?.max ?? null);
          if (cell?.notAvailable) {
            return renderUnavailableCell(t, content, true);
          }
          return h('span', { class: numClass(cell?.max ?? null) }, content);
        },
      },
    ],
  }));

  return [
    {
      title: t('pages.bullMarket.columns.market'),
      dataIndex: 'market',
      width: 88,
    },
    {
      title: t('pages.bullMarket.columns.period'),
      width: 168,
      render: ({ record }) => formatPeriodCompact(record.start, record.end),
    },
    ...indexColumns,
    {
      title: t('pages.bullMarket.columns.turnoverDimensionShort'),
      children: [
        {
          title: t('pages.bullMarket.columns.standardDaysShort'),
          align: 'right',
          width: 56,
          render: ({ record }) =>
            h('span', { class: 'num' }, formatDays(record.turnoverDays)),
        },
        {
          title: t('pages.bullMarket.columns.maxTurnoverShort'),
          align: 'right',
          width: 88,
          render: ({ record }) => {
            const row = record as MergedRow;
            const text =
              row.turnoverMax === null ? '-' : formatAmount(row.turnoverMax);
            return h('span', { class: 'num' }, text);
          },
        },
      ],
    },
  ];
}
