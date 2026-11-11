import { defineComponent, h } from 'vue';
import { mount } from '@vue/test-utils';
import { describe, expect, test } from 'vitest';
import ArcoVue from '@arco-design/web-vue';
import { createI18n } from 'vue-i18n';
import zhCN from '@/locale/zh-CN';
import SyncMetaBadge from '@/components/sync-meta-badge/index.vue';

function mountBadge(props: { failed: boolean; text?: string }) {
  const i18n = createI18n({
    legacy: false,
    locale: 'zh-CN',
    messages: { 'zh-CN': zhCN },
  });
  const Wrapper = defineComponent({
    render: () => h(SyncMetaBadge, { ...props, onRetry: () => undefined }),
  });
  return mount(Wrapper, { global: { plugins: [i18n, ArcoVue] } });
}

describe('SyncMetaBadge', () => {
  test('同步状态就绪时展示文案', () => {
    const wrapper = mountBadge({
      failed: false,
      text: '最新数据日期 2026-11-10',
    });
    expect(wrapper.text()).toContain('最新数据日期 2026-11-10');
    expect(wrapper.find('button').exists()).toBe(false);
  });

  test('同步状态失败时优先展示失败与重试按钮', () => {
    const wrapper = mountBadge({
      failed: true,
      text: '最新数据日期 2026-11-10',
    });
    expect(wrapper.text()).toContain('加载失败');
    expect(wrapper.text()).not.toContain('最新数据日期');
    expect(wrapper.find('button').exists()).toBe(true);
  });

  test('两者都为空时不渲染内容', () => {
    const wrapper = mountBadge({ failed: false, text: '' });
    expect(wrapper.text()).toBe('');
  });
});
