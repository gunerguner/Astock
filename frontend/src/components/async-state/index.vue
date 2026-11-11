<template>
  <div class="async-state">
    <div v-if="showSkeleton" class="async-state-skeleton" :style="frameStyle">
      <a-skeleton animation>
        <a-skeleton-line :rows="rows" :line-height="32" :line-spacing="16" />
      </a-skeleton>
    </div>
    <div
      v-else-if="showError"
      class="async-state-placeholder"
      :style="frameStyle"
    >
      <icon-exclamation-circle-fill class="async-state-icon" />
      <p class="async-state-message">{{ message }}</p>
      <a-button type="primary" @click="emit('retry')">
        {{ t('common.retry') }}
      </a-button>
    </div>
    <div
      v-else-if="showEmpty"
      class="async-state-placeholder"
      :style="frameStyle"
    >
      <p class="async-state-message">{{ emptyText }}</p>
      <a-button type="outline" @click="emit('retry')">
        {{ t('common.retry') }}
      </a-button>
    </div>
    <template v-else>
      <a-alert
        v-if="showStaleAlert"
        class="state-banner"
        type="error"
        :show-icon="true"
      >
        {{ message }}
        <template #action>
          <a-button size="small" type="primary" @click="emit('retry')">
            {{ t('common.retry') }}
          </a-button>
        </template>
      </a-alert>
      <slot />
    </template>
  </div>
</template>

<script lang="ts" setup>
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';
  import describeError from '@/utils/error-message';

  defineOptions({
    name: 'AsyncState',
  });

  const props = withDefaults(
    defineProps<{
      loading: boolean;
      error?: unknown;
      hasData: boolean;
      emptyText?: string;
      rows?: number;
      /** 占位高度：数字按 px，字符串可传 CSS 变量，便于与图表高度共用一处定义 */
      minHeight?: number | string;
      staleAlert?: boolean;
    }>(),
    {
      emptyText: '',
      rows: 8,
      minHeight: 280,
      staleAlert: true,
    },
  );

  const emit = defineEmits<{
    retry: [];
  }>();

  const { t } = useI18n();

  const showSkeleton = computed(() => props.loading && !props.hasData);
  const showError = computed(
    () => !props.loading && Boolean(props.error) && !props.hasData,
  );
  const showEmpty = computed(
    () =>
      !props.loading &&
      !props.error &&
      !props.hasData &&
      Boolean(props.emptyText),
  );
  const showStaleAlert = computed(
    () =>
      props.staleAlert &&
      !props.loading &&
      Boolean(props.error) &&
      props.hasData,
  );
  const frameStyle = computed(() => ({
    minHeight:
      typeof props.minHeight === 'number'
        ? `${props.minHeight}px`
        : props.minHeight,
  }));
  const message = computed(() =>
    describeError(props.error, t('common.loadFailed')),
  );
</script>

<style scoped lang="less">
  .async-state {
    width: 100%;
  }

  .async-state-skeleton {
    width: 100%;
    padding: 8px 0;
  }

  .async-state-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    width: 100%;
    padding: 24px 16px;
    text-align: center;
  }

  .async-state-icon {
    color: rgb(var(--danger-6));
    font-size: 28px;
  }

  .async-state-message {
    margin: 0;
    max-width: 420px;
    color: var(--color-text-2);
    font-size: var(--fs-body);
    line-height: var(--lh-body);
  }
</style>
