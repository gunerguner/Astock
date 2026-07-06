<template>
  <a-tooltip content="刷新全部数据">
    <a-button
      class="nav-btn"
      type="outline"
      shape="circle"
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
    title="确认刷新全部数据"
    ok-text="确认刷新"
    cancel-text="取消"
    :ok-button-props="{ status: 'danger' }"
    :ok-loading="refreshing"
    @ok="handleConfirm"
    @cancel="handleClose"
  >
    <p class="refresh-hint">
      此操作将从外部数据源重新拉取成交额、上证点位与个股切片数据，耗时较长。请输入密码以继续。
    </p>
    <a-input-password
      v-model="inputPassword"
      placeholder="请输入密码"
      allow-clear
      @press-enter="handleConfirm"
    />
  </a-modal>
</template>

<script lang="ts" setup>
  import { ref } from 'vue';
  import { Message } from '@arco-design/web-vue';
  import useAdminDataRefresh from '@/hooks/admin-data-refresh';

  const CONFIRM_PASSWORD = import.meta.env.VITE_ADMIN_REFRESH_PASSWORD ?? '';

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
      Message.error('未配置刷新密码');
      return false;
    }
    if (inputPassword.value !== CONFIRM_PASSWORD) {
      Message.error('密码错误');
      return false;
    }
    handleClose();
    refreshAllData();
    return true;
  }
</script>

<style scoped lang="less">
  .nav-btn {
    border-color: rgb(var(--gray-2));
    color: rgb(var(--gray-8));
    font-size: 16px;
    background-color: transparent;

    &:hover,
    &:focus-visible {
      border-color: rgb(var(--gray-3));
      color: rgb(var(--gray-8));
      background-color: var(--color-fill-2);
    }
  }

  .refresh-hint {
    margin-bottom: 16px;
    font-size: 14px;
    color: var(--color-text-3);
  }
</style>
