import { ref } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, describe, expect, test, vi } from 'vitest';
import ArcoVue from '@arco-design/web-vue';
import ArcoVueIcon from '@arco-design/web-vue/es/icon';
import { createI18n } from 'vue-i18n';
import zhCN from '@/locale/zh-CN';
import AdminRefreshButton from '@/components/admin-refresh-button/index.vue';

const { refreshAllData } = vi.hoisted(() => ({
  refreshAllData: vi.fn(),
}));

vi.mock('@/hooks/admin-data-refresh', () => ({
  default: () => ({
    refreshAllData,
    refreshing: ref(false),
  }),
}));

vi.mock('@/components/refresh-progress-modal/index.vue', () => ({
  default: { name: 'RefreshProgressModal', template: '<div />' },
}));

function mountButton() {
  const i18n = createI18n({
    legacy: false,
    locale: 'zh-CN',
    messages: { 'zh-CN': zhCN },
  });
  return mount(AdminRefreshButton, {
    attachTo: document.body,
    global: { plugins: [i18n, ArcoVue, ArcoVueIcon] },
  });
}

function passwordInput() {
  return document.body.querySelector(
    '.arco-modal input',
  ) as HTMLInputElement | null;
}

async function openAndTypePassword(password: string) {
  const wrapper = mountButton();
  await wrapper.get('button').trigger('click');
  await flushPromises();
  const input = passwordInput();
  if (!input) throw new Error('password input not found');
  input.value = password;
  input.dispatchEvent(new Event('input', { bubbles: true }));
  return wrapper;
}

describe('AdminRefreshButton', () => {
  afterEach(() => {
    document.body.innerHTML = '';
    refreshAllData.mockReset();
  });

  test('回车确认成功后关闭密码浮层', async () => {
    refreshAllData.mockResolvedValue({ accepted: true });
    const wrapper = await openAndTypePassword('secret');

    passwordInput()?.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }),
    );
    await flushPromises();

    expect(refreshAllData).toHaveBeenCalledWith('secret');
    expect(document.body.innerText).not.toContain('确认刷新全部数据');
    wrapper.unmount();
  });

  test('密码错误时回车不关闭浮层', async () => {
    refreshAllData.mockResolvedValue({
      accepted: false,
      message: '密码错误',
    });
    const wrapper = await openAndTypePassword('bad');

    passwordInput()?.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }),
    );
    await flushPromises();

    expect(document.body.innerText).toContain('确认刷新全部数据');
    wrapper.unmount();
  });
});
