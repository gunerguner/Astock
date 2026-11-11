<template>
  <a-alert
    v-if="errors.length"
    class="state-banner"
    type="warning"
    :show-icon="true"
    :title="t('common.partialLoadFailed', { count: errors.length })"
  >
    <ul class="source-error-list">
      <li v-for="(item, index) in errors" :key="`${index}-${item}`">
        {{ item }}
      </li>
    </ul>
  </a-alert>
</template>

<script lang="ts" setup>
  import { useI18n } from 'vue-i18n';

  defineOptions({
    name: 'PartialErrorAlert',
  });

  defineProps<{
    errors: string[];
  }>();

  const { t } = useI18n();
</script>

<style scoped lang="less">
  .source-error-list {
    margin: 4px 0 0;
    padding-left: 18px;
  }
</style>
