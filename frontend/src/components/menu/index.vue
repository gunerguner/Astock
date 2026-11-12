<script lang="tsx" setup>
  import { computed, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';
  import appRoutes from '@/router/routes';

  const props = withDefaults(
    defineProps<{
      mode?: 'horizontal' | 'vertical';
    }>(),
    { mode: 'horizontal' },
  );
  const emit = defineEmits<{
    navigate: [];
  }>();

  const { t } = useI18n();
  const router = useRouter();
  const route = useRoute();
  const selectedKey = ref<string[]>([]);

  const menuItems = computed(() => {
    const root = appRoutes.find((item) => item.name === 'root');
    return (root?.children ?? [])
      .filter((item) => !item.meta?.hideInMenu)
      .sort((a, b) => (a.meta?.order ?? 0) - (b.meta?.order ?? 0));
  });

  watch(
    () => route.name,
    (name) => {
      if (name) selectedKey.value = [String(name)];
    },
    { immediate: true },
  );

  const goto = (name: string) => {
    router.push({ name });
    // 重复点当前页时路由不变，仍需关闭抽屉
    emit('navigate');
  };

  const MenuView = () => (
    <a-menu
      class={props.mode === 'vertical' ? 'drawer-nav-menu' : 'top-nav-menu'}
      mode={props.mode}
      selected-keys={selectedKey.value}
    >
      {menuItems.value.map((item) => (
        <a-menu-item
          key={String(item.name)}
          onClick={() => goto(String(item.name))}
        >
          {t(item.meta?.locale ?? '')}
        </a-menu-item>
      ))}
    </a-menu>
  );
</script>

<template>
  <MenuView />
</template>
