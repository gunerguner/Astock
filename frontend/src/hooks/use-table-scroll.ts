import { computed } from 'vue';
import { useAppStore } from '@/store';

/** 仅移动端启用横向滚动，桌面端表格自适应容器宽度 */
export default function useTableScroll() {
  const appStore = useAppStore();
  return computed(() =>
    appStore.device === 'mobile' ? { x: 'max-content' } : undefined,
  );
}
