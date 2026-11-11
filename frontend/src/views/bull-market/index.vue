<template>
  <div class="page-container">
    <a-card :title="$t('pages.bullMarket.title')" class="section-card">
      <template #extra>
        <SyncMetaBadge
          :failed="syncFailed"
          :text="metaText"
          @retry="loadSyncStatus"
        />
        <span
          v-for="index in indexConfigs"
          :key="index.code"
          class="total-summary"
        >
          {{
            $t('pages.bullMarket.indexStandardDays', {
              name: $t(index.nameKey),
            })
          }}
          <strong>{{ getIndexTotalDays(index.code) }}</strong>
          {{ $t('pages.bullMarket.unitDays') }}
        </span>
        <span class="total-summary">
          {{ $t('pages.bullMarket.turnoverStandardDays') }}
          <strong>{{ turnoverStats?.total_days ?? '-' }}</strong>
          {{ $t('pages.bullMarket.unitDays') }}
        </span>
      </template>
      <a-form
        :model="filterForm"
        class="filter-form"
        layout="inline"
        @submit-success="loadStats"
      >
        <a-form-item
          v-for="index in indexConfigs"
          :key="index.code"
          :label="$t(index.filterKey)"
          :field="`pointThresholds.${index.code}`"
        >
          <a-input-number
            v-model="filterForm.pointThresholds[index.code]"
            :min="1"
            :step="100"
            :precision="0"
            :style="pointInputStyle"
          />
        </a-form-item>
        <a-form-item
          :label="$t('pages.bullMarket.turnoverLabelShort')"
          field="turnoverThresholdTrillion"
        >
          <a-input-number
            v-model="filterForm.turnoverThresholdTrillion"
            :min="0.01"
            :step="0.1"
            :precision="2"
            :style="turnoverInputStyle"
          />
        </a-form-item>
        <a-form-item class="filter-submit">
          <a-button type="primary" html-type="submit" :loading="loading">
            {{ $t('pages.bullMarket.query') }}
          </a-button>
        </a-form-item>
      </a-form>
      <div class="table-wrap">
        <AsyncState
          :loading="loading"
          :error="error"
          :has-data="hasStats"
          :rows="6"
          @retry="loadStats"
        >
          <a-table
            class="result-table"
            :columns="mergedColumns"
            :data="mergedRows"
            :loading="loading && hasStats"
            :pagination="false"
            :scroll="tableScroll"
            row-key="market"
          />
        </AsyncState>
      </div>
    </a-card>
  </div>
</template>

<script lang="ts" setup>
  import { computed } from 'vue';
  import AsyncState from '@/components/async-state/index.vue';
  import SyncMetaBadge from '@/components/sync-meta-badge/index.vue';
  import usePageRefresh from '@/hooks/use-page-refresh';
  import { useIsCompact } from '@/hooks/responsive';
  import useSyncStatus from '@/hooks/use-sync-status';
  import useTableScroll from '@/hooks/use-table-scroll';
  import useBullMarket from './use-bull-market';

  defineOptions({
    name: 'BullMarket',
  });

  const tableScroll = useTableScroll();
  const isCompact = useIsCompact();
  const pointInputStyle = computed(() => ({
    width: isCompact.value ? '100%' : '120px',
  }));
  const turnoverInputStyle = computed(() => ({
    width: isCompact.value ? '100%' : '140px',
  }));
  const {
    metaText,
    loadFailed: syncFailed,
    loadSyncStatus,
  } = useSyncStatus('point', 'turnover');
  const {
    indexConfigs,
    filterForm,
    loading,
    error,
    hasStats,
    loadStats,
    turnoverStats,
    mergedRows,
    mergedColumns,
    getIndexTotalDays,
  } = useBullMarket();

  usePageRefresh(() => {
    loadStats();
    loadSyncStatus();
  });
</script>

<style scoped lang="less">
  .section-card {
    margin-bottom: 16px;
  }

  .total-summary {
    display: inline-flex;
    align-items: center;
    color: var(--color-text-2);
    font-size: var(--fs-body);
    line-height: var(--lh-title);
    margin-left: 0;

    strong {
      color: var(--brand-6);
      font-size: var(--fs-title);
      font-variant-numeric: tabular-nums;
      font-feature-settings: 'tnum';
    }
  }

  .table-wrap {
    margin-top: 8px;
  }

  .result-table {
    :deep(.arco-table-th),
    :deep(.arco-table-td) {
      padding-left: 8px;
      padding-right: 8px;
    }

    :deep(.arco-table-cell) {
      padding: 8px 4px;
      font-size: var(--fs-body);
    }
  }

  .filter-form {
    display: flex;
    flex-wrap: nowrap;
    align-items: center;
    gap: 0;
    margin-bottom: 24px;

    :deep(.arco-form-item) {
      margin-bottom: 0;
      margin-right: 12px;
      flex-shrink: 0;
    }

    @media (max-width: @screen-compact-max) {
      flex-wrap: wrap;

      :deep(.arco-form-item) {
        flex: 1 1 100%;
        width: 100%;
        margin-right: 0;
        margin-bottom: 12px;
      }

      :deep(.arco-form-item-content) {
        flex: 1;
        min-width: 0;
      }
    }

    :deep(.arco-form-item-label) {
      padding-right: 6px;
      font-size: var(--fs-body);
      white-space: nowrap;
    }

    :deep(.arco-form-item-label-col) {
      flex: none;
    }

    .filter-submit {
      margin-right: 0;
    }
  }

  :deep(.unavailable) {
    color: var(--color-text-3);
    cursor: help;
  }
</style>
