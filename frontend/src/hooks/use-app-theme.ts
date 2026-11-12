import { useDark } from '@vueuse/core';

/** 与 Arco 主题属性、本地存储键对齐的暗色开关。 */
export default function useAppDark() {
  return useDark({
    selector: 'body',
    attribute: 'arco-theme',
    valueDark: 'dark',
    valueLight: 'light',
    storageKey: 'arco-theme',
  });
}
