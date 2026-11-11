<template>
  <span v-if="failed" class="meta-text meta-text-error">
    {{ t('common.loadFailed') }}
    <a-button class="meta-retry" type="text" size="mini" @click="emit('retry')">
      {{ t('common.retry') }}
    </a-button>
  </span>
  <span v-else-if="text" class="meta-text">{{ text }}</span>
</template>

<script lang="ts" setup>
  import { useI18n } from 'vue-i18n';

  defineOptions({
    name: 'SyncMetaBadge',
  });

  defineProps<{
    /** 同步状态接口失败：优先展示失败与重试，替代同步时间文案 */
    failed: boolean;
    /** 已就绪的同步状态文案，为空时不渲染 */
    text?: string;
  }>();

  const emit = defineEmits<{
    retry: [];
  }>();

  const { t } = useI18n();
</script>

<style scoped lang="less">
  .meta-text-error {
    color: rgb(var(--danger-6));

    &::before {
      background-color: rgb(var(--danger-6));
    }
  }

  .meta-retry {
    height: auto;
    margin-left: 4px;
    padding: 0 4px;
  }
</style>
