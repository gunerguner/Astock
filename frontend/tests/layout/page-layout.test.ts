import { defineComponent, h } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { createMemoryHistory, createRouter } from 'vue-router';
import { beforeEach, describe, expect, test } from 'vitest';

import PageLayout from '@/layout/page-layout.vue';

const setups = { a: 0, b: 0 };

const PageA = defineComponent({
  name: 'PageA',
  setup() {
    setups.a += 1;
    return () => h('div', 'A');
  },
});

const PageB = defineComponent({
  name: 'PageB',
  setup() {
    setups.b += 1;
    return () => h('div', 'B');
  },
});

describe('page layout keep-alive', () => {
  beforeEach(() => {
    setups.a = 0;
    setups.b = 0;
  });

  test('再次进入已访问页面时不重新 setup', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/a', component: PageA },
        { path: '/b', component: PageB },
      ],
    });
    await router.push('/a');
    await router.isReady();

    const wrapper = mount(PageLayout, {
      global: { plugins: [router] },
    });
    await flushPromises();
    expect(setups).toEqual({ a: 1, b: 0 });

    await router.push('/b');
    await flushPromises();
    expect(setups).toEqual({ a: 1, b: 1 });

    await router.push('/a');
    await flushPromises();
    expect(setups).toEqual({ a: 1, b: 1 });

    wrapper.unmount();
  });
});
