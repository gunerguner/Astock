import { useMediaQuery } from '@vueuse/core';

/** 手机：Arco Grid md（768）以下 */
export const MOBILE_QUERY = '(max-width: 767px)';

/** 平板/紧凑：Arco Grid lg（992）以下，与 global.less 紧凑样式对齐 */
export const COMPACT_QUERY = '(max-width: 991px)';

export function useIsMobile() {
  return useMediaQuery(MOBILE_QUERY);
}

export function useIsCompact() {
  return useMediaQuery(COMPACT_QUERY);
}

/**
 * 窄屏下 Arco 会按内容压缩没有宽度的列，表格列会被压成竖排文字。
 * 仅在手机宽度给出固定列宽，桌面端返回空对象以保持自适应。
 */
export function mobileColumn(
  isMobile: boolean,
  width: number,
  fixed: 'left' | 'right' | false = false,
) {
  if (!isMobile) return {};
  return fixed ? { width, fixed } : { width };
}
