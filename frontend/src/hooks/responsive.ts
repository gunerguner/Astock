import { onMounted, onBeforeMount, onBeforeUnmount } from 'vue';
import { useDebounceFn } from '@vueuse/core';
import { useAppStore } from '@/store';
import { addEventListen, removeEventListen } from '@/utils/event';

// Keep in sync with global.less `@media (max-width: 992px)` and Arco Grid md.
const WIDTH = 992; // https://arco.design/vue/component/grid#responsivevalue

function queryDevice() {
  const rect = document.body.getBoundingClientRect();
  return rect.width - 1 < WIDTH;
}

export default function useResponsive(immediate?: boolean) {
  const appStore = useAppStore();
  function resizeHandler() {
    if (!document.hidden) {
      const isMobile = queryDevice();
      appStore.toggleDevice(isMobile ? 'mobile' : 'desktop');
    }
  }
  const debounceFn = useDebounceFn(resizeHandler, 100);
  onMounted(() => {
    if (immediate) debounceFn();
  });
  onBeforeMount(() => {
    addEventListen(window, 'resize', debounceFn);
  });
  onBeforeUnmount(() => {
    removeEventListen(window, 'resize', debounceFn);
  });
}
