<template>
  <div class="navbar">
    <div class="left-side">
      <a-space :size="12">
        <icon-public class="brand-icon" />
        <div class="brand-group">
          <a-typography-title class="brand-title" :heading="5">
            {{ $t('navbar.brand.title') }}
          </a-typography-title>
        </div>
      </a-space>
    </div>
    <div v-if="showMenu" class="center-side">
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
            theme === 'light'
              ? $t('settings.navbar.theme.toDark')
              : $t('settings.navbar.theme.toLight')
          "
        >
          <a-button
            class="nav-btn-ghost"
            type="text"
            @click="handleToggleTheme"
          >
            <template #icon>
              <icon-moon-fill v-if="theme === 'dark'" />
              <icon-sun-fill v-else />
            </template>
          </a-button>
        </a-tooltip>
      </li>
    </ul>
  </div>
</template>

<script lang="ts" setup>
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useDark, useToggle } from '@vueuse/core';
  import { useAppStore } from '@/store';
  import useLocale from '@/hooks/locale';
  import Menu from '@/components/menu/index.vue';
  import AdminRefreshButton from '@/components/admin-refresh-button/index.vue';

  const appStore = useAppStore();
  const { t } = useI18n();
  const { currentLocale, toggleLocale } = useLocale();
  const theme = computed(() => appStore.theme);
  const showMenu = computed(() => appStore.menu);
  const localeToggleHint = computed(() =>
    currentLocale.value === 'zh-CN'
      ? t('navbar.action.switchToEn')
      : t('navbar.action.switchToZh')
  );
  const isDark = useDark({
    selector: 'body',
    attribute: 'arco-theme',
    valueDark: 'dark',
    valueLight: 'light',
    storageKey: 'arco-theme',
    onChanged(dark: boolean) {
      appStore.toggleTheme(dark);
    }
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
</style>
