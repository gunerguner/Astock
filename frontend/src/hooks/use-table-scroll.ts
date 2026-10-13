import { computed } from 'vue';
import { useMediaQuery } from '@vueuse/core';

/** 与 global.less `@media (max-width: 992px)` 以及 Arco Grid md 对齐 */
const MOBILE_QUERY = '(max-width: 992px)';

/** 仅移动端启用横向滚动，桌面端表格自适应容器宽度 */
export default function useTableScroll() {
  const isMobile = useMediaQuery(MOBILE_QUERY);
  return computed(() => (isMobile.value ? { x: 'max-content' } : undefined));
}
