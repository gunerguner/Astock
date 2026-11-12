import { h, type VNode } from 'vue';
import { Tag } from '@arco-design/web-vue';
import type { TableColumnData, TableData } from '@arco-design/web-vue';
import type { ComposerTranslation } from 'vue-i18n';
import { isPriceLevelPending } from '@/api/analysis';
import { mobileColumn } from '@/hooks/responsive';
import {
  isDividerRow,
  toTableRow,
  type BaseDividerRow,
} from '@/hooks/grouped-table';
import { CONCLUSION_I18N_KEYS } from '@/utils/format';
import renderAssetNameWithTooltip from '@/utils/render-asset-cell';
import {
  renderNumCell,
  renderPendingDash,
  renderPercentCell,
  renderPlainPriceCell,
  renderPriceCell,
} from '@/utils/table-cells';

/** 七姐妹 + SpaceX */
const FOCUSED_TICKERS = new Set([
  'AAPL',
  'MSFT',
  'GOOGL',
  'AMZN',
  'NVDA',
  'META',
  'TSLA',
  'SPCX',
]);

type DividerRow = BaseDividerRow;
export type ErrorRow = {
  key: string;
  rowKind: 'error';
  ticker: string;
  name: string;
  message: string;
};
export type AssetTableRow =
  (API.PriceLevelRow & { key: string }) | DividerRow | ErrorRow;

const isErrorRow = (row: AssetTableRow): row is ErrorRow =>
  'rowKind' in row && row.rowKind === 'error';

const CONCLUSION_COLORS: Record<API.PriceLevelConclusion, string> = {
  pending: 'gray',
  nearAth: 'arcoblue',
  moderatePullback: 'gold',
  significantPullback: 'orangered',
  deepPullback: 'red',
};

type SettledRow = API.PriceLevelDataItem & { key: string };

function guardDataRow(record: TableData) {
  const row = toTableRow<AssetTableRow>(record);
  if (isDividerRow(row)) return null;
  if (isErrorRow(row)) return 'error' as const;
  if (isPriceLevelPending(row)) return 'pending' as const;
  return row;
}

const isPlaceholderRow = (
  row: ReturnType<typeof guardDataRow>,
): row is 'pending' | 'error' => row === 'pending' || row === 'error';

function dataColumn(
  title: string,
  width: number,
  isMobile: boolean,
  renderValue: (row: SettledRow) => VNode | string,
): TableColumnData {
  return {
    title,
    align: 'right',
    ...mobileColumn(isMobile, width),
    render: ({ record }: { record: TableData }) => {
      const row = guardDataRow(record);
      if (!row || isPlaceholderRow(row)) return renderPendingDash();
      return renderValue(row);
    },
  };
}

function renderAssetCell(t: ComposerTranslation, record: API.PriceLevelRow) {
  return renderAssetNameWithTooltip(record.name, record.ticker, () =>
    FOCUSED_TICKERS.has(record.ticker)
      ? h(
          Tag,
          {
            color: 'arcoblue',
            size: 'small',
            class: 'focus-tag',
            style: { marginLeft: '8px' },
          },
          () => t('pages.assetPriceLevels.focusedTag'),
        )
      : null,
  );
}

export default function buildAssetColumns(
  t: ComposerTranslation,
  isMobile: boolean,
): TableColumnData[] {
  return [
    {
      title: t('pages.assetPriceLevels.columns.asset'),
      ...mobileColumn(isMobile, 132, 'left'),
      render: ({ record }: { record: TableData }) => {
        const row = toTableRow<AssetTableRow>(record);
        if (isDividerRow(row)) {
          return h('span', { class: 'section-divider-label' }, row.label);
        }
        if (isErrorRow(row)) {
          return renderAssetNameWithTooltip(row.name, row.message);
        }
        return renderAssetCell(t, row);
      },
    },
    dataColumn(
      t('pages.assetPriceLevels.columns.currentPrice'),
      104,
      isMobile,
      (row) => renderPriceCell(row.current_price),
    ),
    dataColumn(
      t('pages.assetPriceLevels.columns.athPrice'),
      104,
      isMobile,
      (row) => renderPlainPriceCell(row.all_time_high),
    ),
    dataColumn(
      t('pages.assetPriceLevels.columns.athDiff'),
      96,
      isMobile,
      (row) => renderPercentCell(row.percentage_diff),
    ),
    dataColumn(
      t('pages.assetPriceLevels.columns.athDays'),
      104,
      isMobile,
      (row) => renderNumCell(String(row.ath_days)),
    ),
    dataColumn(
      t('pages.assetPriceLevels.columns.dailyChange'),
      88,
      isMobile,
      (row) => renderPercentCell(row.daily_change),
    ),
    dataColumn(
      t('pages.assetPriceLevels.columns.weeklyChange'),
      88,
      isMobile,
      (row) => renderPercentCell(row.weekly_change),
    ),
    {
      title: t('pages.assetPriceLevels.columns.conclusion'),
      ...mobileColumn(isMobile, 96),
      render: ({ record }: { record: TableData }) => {
        const raw = toTableRow<AssetTableRow>(record);
        if (isErrorRow(raw)) return raw.message;
        const row = guardDataRow(record);
        if (!row || isPlaceholderRow(row)) {
          return h(Tag, { color: 'gray' }, () =>
            t('pages.assetPriceLevels.conclusion.pending'),
          );
        }
        return h(Tag, { color: CONCLUSION_COLORS[row.conclusion] }, () =>
          t(CONCLUSION_I18N_KEYS[row.conclusion]),
        );
      },
    },
  ];
}
