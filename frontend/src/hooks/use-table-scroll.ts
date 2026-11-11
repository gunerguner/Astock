import { computed } from 'vue';
import { useIsCompact } from '@/hooks/responsive';

/** 仅紧凑宽度启用横向滚动，桌面端表格自适应容器宽度 */
export default function useTableScroll() {
  const isCompact = useIsCompact();
  return computed(() => (isCompact.value ? { x: 'max-content' } : undefined));
}
