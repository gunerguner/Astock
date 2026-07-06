<template>
  <div class="navbar">
    <div class="left-side">
      <a-space>
        <icon-public class="brand-icon" />
        <a-typography-title
          :style="{ margin: 0, fontSize: '18px' }"
          :heading="5"
        >
          全球投资信息平台
        </a-typography-title>
        <icon-menu-fold
          v-if="!topMenu && appStore.device === 'mobile'"
          style="font-size: 22px; cursor: pointer"
          @click="toggleDrawerMenu"
        />
      </a-space>
    </div>
    <div class="center-side">
      <Menu v-if="topMenu" />
    </div>
    <ul class="right-side">
      <li>
        <a-dropdown
          trigger="click"
          @select="(val) => changeLocale(val as string)"
        >
          <a-button class="nav-btn" type="outline" :shape="'circle'">
            <template #icon>
              <icon-language />
            </template>
          </a-button>
          <template #content>
            <a-doption
              v-for="item in LOCALE_OPTIONS"
              :key="item.value"
              :value="item.value"
            >
              <template #icon>
                <icon-check v-show="item.value === currentLocale" />
              </template>
              {{ item.label }}
            </a-doption>
          </template>
        </a-dropdown>
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
            class="nav-btn"
            type="outline"
            :shape="'circle'"
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
  import { computed, inject } from 'vue';
  import { useDark, useToggle } from '@vueuse/core';
  import { useAppStore } from '@/store';
  import useLocale from '@/hooks/locale';
  import { LOCALE_OPTIONS } from '@/locale';
  import Menu from '@/components/menu/index.vue';

  const appStore = useAppStore();
  const { currentLocale, changeLocale } = useLocale();
  const theme = computed(() => appStore.theme);
  const topMenu = computed(() => appStore.topMenu && appStore.menu);
  const isDark = useDark({
    selector: 'body',
    attribute: 'arco-theme',
    valueDark: 'dark',
    valueLight: 'light',
    storageKey: 'arco-theme',
    onChanged(dark: boolean) {
      appStore.toggleTheme(dark);
    },
  });
  const toggleTheme = useToggle(isDark);
  const handleToggleTheme = () => {
    toggleTheme();
  };
  const toggleDrawerMenu = inject('toggleDrawerMenu') as () => void;
</script>

<style scoped lang="less">
  .navbar {
    display: flex;
    justify-content: space-between;
    height: 100%;
    background-color: var(--color-bg-2);
    border-bottom: 1px solid var(--color-border);
  }

  .left-side {
    display: flex;
    align-items: center;
    padding-left: 20px;

    .brand-icon {
      font-size: 22px;
      color: rgb(var(--primary-6));
    }
  }

  .center-side {
    flex: 1;
  }

  .right-side {
    display: flex;
    padding-right: 20px;
    list-style: none;

    li {
      display: flex;
      align-items: center;
      padding: 0 10px;
    }

    .nav-btn {
      border-color: rgb(var(--gray-2));
      color: rgb(var(--gray-8));
      font-size: 16px;
    }
  }
</style>
