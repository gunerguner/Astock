<template>
  <a-modal
    :visible="visible"
    :title="$t('adminRefresh.progress.title')"
    :mask-closable="false"
    :closable="false"
    :esc-to-close="false"
    :footer="false"
    :mask="true"
    :unmount-on-close="true"
    width="640px"
  >
    <div class="progress-summary">
      <div class="progress-summary__label">
        {{ $t('adminRefresh.progress.overall') }}
        <span class="progress-summary__count">
          {{ progressState.completedCount }}/{{ progressState.totalPhases }}
        </span>
      </div>
    </div>

    <div class="phase-list">
      <div
        v-for="phaseKey in phaseOrder"
        :key="phaseKey"
        class="phase-row"
        :class="`phase-row--${progressState.phases[phaseKey].status}`"
      >
        <span class="phase-row__icon">{{ phaseIcon(phaseKey) }}</span>
        <span class="phase-row__name">
          {{ progressState.phases[phaseKey].label }}
        </span>
        <span class="phase-row__metric">
          {{ phaseMetric(phaseKey) }}
        </span>
        <span class="phase-row__elapsed">
          {{ formatElapsed(progressState.phases[phaseKey].elapsed) }}
        </span>
        <span class="phase-row__status">
          {{ phaseStatusText(phaseKey) }}
        </span>
      </div>
    </div>

    <a-collapse
      v-if="errorDetails.length > 0"
      :default-active-key="['errors']"
      class="error-collapse"
    >
      <a-collapse-item
        key="errors"
        :header="$t('adminRefresh.progress.errorDetails')"
      >
        <pre class="error-details">{{ errorDetails.join('\n') }}</pre>
      </a-collapse-item>
    </a-collapse>

    <p v-if="progressState.errorMessage" class="error-message">
      {{ progressState.errorMessage }}
    </p>

    <div v-if="canClose" class="modal-footer">
      <a-button type="primary" @click="handleClose">
        {{ $t('adminRefresh.progress.close') }}
      </a-button>
    </div>
  </a-modal>
</template>

<script lang="ts" setup>
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';
  import useAdminDataRefresh from '@/hooks/admin-data-refresh';
  import {
    PHASE_ORDER,
    type PhaseKey,
    type PhaseStatus,
  } from '@/hooks/admin-data-refresh.types';

  const { t } = useI18n();
  const { progressVisible, progressState, closeProgressModal, refreshing } =
    useAdminDataRefresh();

  const visible = computed(() => progressVisible.value);
  const phaseOrder = PHASE_ORDER;

  const canClose = computed(
    () =>
      !refreshing.value &&
      (progressState.value.overallStatus === 'done' ||
        progressState.value.overallStatus === 'error')
  );

  const errorDetails = computed(() => {
    const lines: string[] = [];
    phaseOrder.forEach((key) => {
      const item = progressState.value.phases[key];
      if (!item.source_errors) return;
      Object.entries(item.source_errors).forEach(([source, message]) => {
        if (message) {
          lines.push(`${item.label}(${source}): ${message}`);
        }
      });
    });
    return lines;
  });

  function phaseIcon(key: PhaseKey): string {
    const { status } = progressState.value.phases[key];
    if (status === 'done') return '✓';
    if (status === 'running') return '⟳';
    if (status === 'failed') return '✗';
    return '·';
  }

  function phaseMetric(key: PhaseKey): string {
    const item = progressState.value.phases[key];
    if (item.status === 'pending') return '—';
    // 个股切片：进行中按缺口交易日进度；完成/失败与其它阶段一致显示写入行数
    if (key === 'stock' && item.status === 'running' && item.total > 0) {
      return `${item.current}/${item.total.toLocaleString()} ${t(
        'adminRefresh.progress.days'
      )}`;
    }
    if (
      item.imported > 0 ||
      item.status === 'done' ||
      item.status === 'failed'
    ) {
      return `${item.imported.toLocaleString()} ${t(
        'adminRefresh.progress.rows'
      )}`;
    }
    return item.detail || '—';
  }

  function formatElapsed(elapsed?: number): string {
    if (elapsed == null) return '—';
    return `${elapsed.toFixed(1)}s`;
  }

  function phaseStatusText(key: PhaseKey): string {
    const { status } = progressState.value.phases[key];
    const map: Record<PhaseStatus, string> = {
      pending: t('adminRefresh.progress.status.pending'),
      running: t('adminRefresh.progress.status.running'),
      done: t('adminRefresh.progress.status.done'),
      failed: t('adminRefresh.progress.status.failed'),
    };
    return map[status];
  }

  function handleClose() {
    closeProgressModal();
  }
</script>

<style scoped lang="less">
  .progress-summary {
    margin-bottom: 20px;

    &__label {
      display: flex;
      justify-content: space-between;
      font-size: var(--fs-body);
      color: var(--color-text-2);
    }

    &__count {
      color: var(--color-text-3);
    }
  }

  .phase-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .phase-row {
    display: grid;
    grid-template-columns: 24px 1fr 120px 56px 72px;
    gap: 8px;
    align-items: center;
    padding: 8px 10px;
    border-radius: 6px;
    background: var(--color-fill-1);
    font-size: var(--fs-body);

    &--running,
    &--done {
      background: rgb(var(--primary-1));
    }

    &--failed {
      background: rgb(var(--danger-1));
    }

    &__icon {
      text-align: center;
      font-weight: 600;
    }

    &__name {
      color: var(--color-text-1);
    }

    &__metric,
    &__elapsed,
    &__status {
      color: var(--color-text-3);
      text-align: right;
      white-space: nowrap;
    }
  }

  .error-collapse {
    margin-top: 16px;
  }

  .error-details {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
    font-size: 12px;
    color: var(--color-text-2);
  }

  .error-message {
    margin-top: 12px;
    color: rgb(var(--danger-6));
    font-size: var(--fs-body);
  }

  .modal-footer {
    display: flex;
    justify-content: flex-end;
    margin-top: 20px;
  }
</style>
