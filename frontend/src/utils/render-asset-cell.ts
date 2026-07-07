import { h, type VNode } from 'vue';
import { Tooltip } from '@arco-design/web-vue';

export default function renderAssetNameWithTooltip(
  name: string,
  code: string,
  extra?: () => VNode | null
) {
  return h(
    Tooltip,
    { content: code, position: 'top' },
    {
      default: () =>
        h('span', { class: 'asset-name-cell' }, [
          h('span', { class: 'asset-name-text asset-name-hover' }, name),
          extra?.(),
        ]),
    }
  );
}
