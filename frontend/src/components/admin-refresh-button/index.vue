<template>
  <a-tooltip :content="$t('adminRefresh.tooltip')">
    <a-button
      class="nav-btn-ghost"
      type="text"
      :disabled="refreshing"
      @click="openConfirmModal"
    >
      <template #icon>
        <icon-refresh :spin="refreshing" />
      </template>
    </a-button>
  </a-tooltip>

  <a-modal
    v-model:visible="modalVisible"
    :title="$t('adminRefresh.modalTitle')"
    :ok-text="$t('adminRefresh.okText')"
    :cancel-text="$t('adminRefresh.cancelText')"
    :ok-button-props="{ status: 'danger' }"
    @ok="handleConfirm"
    @cancel="handleClose"
  >
    <p class="refresh-hint">{{ $t('adminRefresh.hint') }}</p>
    <a-input-password
      v-model="inputPassword"
      :placeholder="$t('adminRefresh.passwordPlaceholder')"
      allow-clear
      @press-enter="handleConfirm"
    />
  </a-modal>

  <RefreshProgressModal />
</template>

<script lang="ts" setup>
  import { ref } from 'vue';
  import { Message } from '@arco-design/web-vue';
  import { useI18n } from 'vue-i18n';
  import RefreshProgressModal from '@/components/refresh-progress-modal/index.vue';
  import useAdminDataRefresh from '@/hooks/admin-data-refresh';

  const CONFIRM_PASSWORD = import.meta.env.VITE_ADMIN_REFRESH_PASSWORD ?? '';

  const { t } = useI18n();
  const { refreshAllData, refreshing } = useAdminDataRefresh();
  const modalVisible = ref(false);
  const inputPassword = ref('');

  function openConfirmModal() {
    if (refreshing.value) return;
    inputPassword.value = '';
    modalVisible.value = true;
  }

  function handleClose() {
    modalVisible.value = false;
    inputPassword.value = '';
  }

  function handleConfirm() {
    if (!CONFIRM_PASSWORD) {
      Message.error(t('adminRefresh.missingPassword'));
      return false;
    }
    if (inputPassword.value !== CONFIRM_PASSWORD) {
      Message.error(t('adminRefresh.wrongPassword'));
      return false;
    }
    handleClose();
    refreshAllData();
    return true;
  }
</script>

<style scoped lang="less">
  .refresh-hint {
    margin-bottom: 16px;
    font-size: var(--fs-body);
    color: var(--color-text-3);
  }
</style>
