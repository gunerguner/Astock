<script lang="tsx">
  import { computed, defineComponent, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { useRoute, useRouter } from 'vue-router';
  import appRoutes from '@/router/routes';

  export default defineComponent({
    setup() {
      const { t } = useI18n();
      const router = useRouter();
      const route = useRoute();
      const selectedKey = ref<string[]>([]);

      const menuItems = computed(() => {
        const root = appRoutes.find((item) => item.name === 'root');
        return (root?.children ?? [])
          .filter((item) => !item.meta?.hideInMenu)
          .sort((a, b) => (a.meta?.order || 0) - (b.meta?.order || 0));
      });

      watch(
        () => route.name,
        (name) => {
          if (name) {
            selectedKey.value = [String(name)];
          }
        },
        { immediate: true },
      );

      const goto = (name: string) => {
        router.push({ name });
      };

      return () => (
        <a-menu
          class="top-nav-menu"
          mode="horizontal"
          selected-keys={selectedKey.value}
        >
          {menuItems.value.map((item) => (
            <a-menu-item
              key={String(item.name)}
              onClick={() => goto(String(item.name))}
            >
              {t(item.meta?.locale || '')}
            </a-menu-item>
          ))}
        </a-menu>
      );
    },
  });
</script>
