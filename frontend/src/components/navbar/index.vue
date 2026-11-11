<template>
  <div class="navbar">
    <div class="left-side">
      <a-button
        v-if="isMobile"
        class="nav-btn-ghost"
        type="text"
        :aria-label="$t('navbar.action.openMenu')"
        @click="drawerVisible = true"
      >
        <template #icon>
          <icon-menu />
        </template>
      </a-button>
      <a-space :size="12">
        <icon-public class="brand-icon" />
        <div class="brand-group">
          <a-typography-title class="brand-title" :heading="5">
            {{ $t('navbar.brand.title') }}
          </a-typography-title>
        </div>
      </a-space>
    </div>
    <div v-if="!isMobile" class="center-side">
      <Menu />
    </div>
    <ul class="right-side">
      <li>
        <AdminRefreshButton />
      </li>
      <li>
        <a-tooltip :content="localeToggleHint">
          <a-button class="nav-btn-ghost" type="text" @click="toggleLocale">
            <template #icon>
              <icon-language />
            </template>
          </a-button>
        </a-tooltip>
      </li>
      <li>
        <a-tooltip
          :content="
            isDark
              ? $t('settings.navbar.theme.toLight')
              : $t('settings.navbar.theme.toDark')
          "
        >
          <a-button
            class="nav-btn-ghost"
            type="text"
            @click="handleToggleTheme"
          >
            <template #icon>
              <icon-moon-fill v-if="isDark" />
              <icon-sun-fill v-else />
            </template>
          </a-button>
        </a-tooltip>
      </li>
    </ul>
    <a-drawer
      v-model:visible="drawerVisible"
      placement="left"
      :width="260"
      :footer="false"
      :title="$t('navbar.brand.title')"
      :body-style="{ padding: '8px 12px' }"
      unmount-on-close
    >
      <Menu mode="vertical" @navigate="drawerVisible = false" />
    </a-drawer>
  </div>
</template>

<script lang="ts" setup>
  import { computed, ref, watch } from 'vue';
  import { useRoute } from 'vue-router';
  import { useI18n } from 'vue-i18n';
  import { useDark, useToggle } from '@vueuse/core';
  import useLocale from '@/hooks/locale';
  import { useIsMobile } from '@/hooks/responsive';
  import Menu from '@/components/menu/index.vue';
  import AdminRefreshButton from '@/components/admin-refresh-button/index.vue';

  const route = useRoute();
  const isMobile = useIsMobile();
  const drawerVisible = ref(false);

  // 浏览器前进/后退切换页面时收起抽屉
  watch(
    () => route.fullPath,
    () => {
      drawerVisible.value = false;
    },
  );

  // 视口变宽切回横向菜单时收起抽屉
  watch(isMobile, (mobile) => {
    if (!mobile) drawerVisible.value = false;
  });

  const { t } = useI18n();
  const { currentLocale, toggleLocale } = useLocale();
  const localeToggleHint = computed(() =>
    currentLocale.value === 'zh-CN'
      ? t('navbar.action.switchToEn')
      : t('navbar.action.switchToZh'),
  );
  const isDark = useDark({
    selector: 'body',
    attribute: 'arco-theme',
    valueDark: 'dark',
    valueLight: 'light',
    storageKey: 'arco-theme',
  });
  const toggleTheme = useToggle(isDark);
  const handleToggleTheme = () => {
    toggleTheme();
  };
</script>

<style scoped lang="less">
  .navbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    height: 100%;
    background-color: var(--color-bg-2);
    border-bottom: 1px solid var(--color-border-2);
  }

  .left-side {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    padding-left: 16px;
  }

  .brand-icon {
    font-size: 20px;
    color: var(--brand-6);
  }

  .brand-group {
    display: flex;
    align-items: center;
  }

  .brand-title {
    margin: 0 !important;
    font-size: var(--fs-h5) !important;
    line-height: var(--lh-h5) !important;
    font-weight: 600;
    white-space: nowrap;
  }

  .center-side {
    display: flex;
    align-items: center;
    flex: 1;
    min-width: 0;
    height: 100%;
    overflow-x: auto;
    overflow-y: hidden;

    &::-webkit-scrollbar {
      display: none;
    }
  }

  .right-side {
    display: flex;
    flex-shrink: 0;
    padding-right: 16px;
    list-style: none;

    li {
      display: flex;
      align-items: center;
      padding: 0 6px;
    }
  }

  @media (max-width: @screen-mobile-max) {
    .navbar {
      gap: 8px;
    }

    .left-side {
      flex: 1;
      min-width: 0;
      padding-left: 8px;
    }

    .left-side :deep(.arco-space) {
      min-width: 0;
      max-width: 100%;
    }

    .brand-group {
      min-width: 0;
    }

    .brand-title {
      overflow: hidden;
      font-size: var(--fs-title) !important;
      line-height: var(--lh-title) !important;
      text-overflow: ellipsis;
    }

    .right-side {
      padding-right: 8px;

      li {
        padding: 0 2px;
      }
    }
  }
</style>
