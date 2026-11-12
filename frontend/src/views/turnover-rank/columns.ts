import type { TableColumnData, TableData } from '@arco-design/web-vue';
import type { ComposerTranslation } from 'vue-i18n';
import { mobileColumn } from '@/hooks/responsive';
import { toTableRow } from '@/hooks/grouped-table';
import { formatAmount } from '@/utils/format';
import { renderNumCell } from '@/utils/table-cells';

const MARKET_AMOUNT_COLUMNS = [
  ['sh', 'sse_amount', 110],
  ['sz', 'szse_amount', 110],
  ['total', 'turnover', 120],
] as const;

function rankColumn(
  t: ComposerTranslation,
  isMobile: boolean,
): TableColumnData {
  return {
    title: t('pages.turnoverRank.columns.rank'),
    dataIndex: 'rank',
    width: 72,
    align: 'right',
    ...mobileColumn(isMobile, 72, 'left'),
  };
}

function dateColumn(t: ComposerTranslation): TableColumnData {
  return {
    title: t('pages.turnoverRank.columns.date'),
    dataIndex: 'date',
    width: 118,
  };
}

export function buildMarketColumns(
  t: ComposerTranslation,
  isMobile: boolean,
): TableColumnData[] {
  const amountColumns = MARKET_AMOUNT_COLUMNS.map(
    ([key, field, width]): TableColumnData => ({
      title: t(`pages.turnoverRank.columns.${key}`),
      align: 'right',
      width,
      render: ({ record }: { record: TableData }) => {
        const row = toTableRow<API.TurnoverRankingItem>(record);
        return renderNumCell(formatAmount(row[field]));
      },
    }),
  );
  return [rankColumn(t, isMobile), dateColumn(t), ...amountColumns];
}

export function buildStockColumns(
  t: ComposerTranslation,
  isMobile: boolean,
): TableColumnData[] {
  return [
    rankColumn(t, isMobile),
    dateColumn(t),
    {
      title: t('pages.turnoverRank.columns.stockName'),
      dataIndex: 'name',
      width: 120,
    },
    {
      title: t('pages.turnoverRank.columns.stockCode'),
      dataIndex: 'code',
      width: 96,
    },
    {
      title: t('pages.turnoverRank.columns.turnover'),
      align: 'right',
      width: 120,
      render: ({ record }: { record: TableData }) => {
        const row = toTableRow<API.StockRankingItem>(record);
        return renderNumCell(formatAmount(row.amount));
      },
    },
  ];
}
