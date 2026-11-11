import { defineComponent, h } from 'vue';
import { mount } from '@vue/test-utils';
import { afterEach, describe, expect, it } from 'vitest';
import {
  COMPACT_QUERY,
  MOBILE_QUERY,
  useIsCompact,
  useIsMobile,
} from '@/hooks/responsive';
import useTableScroll from '@/hooks/use-table-scroll';

const originalMatchMedia = window.matchMedia;

function noop() {
  return undefined;
}

function installMatchMedia(matchesFor: (query: string) => boolean) {
  window.matchMedia = ((query: string) => ({
    matches: matchesFor(query),
    media: query,
    onchange: null,
    addListener: noop,
    removeListener: noop,
    addEventListener: noop,
    removeEventListener: noop,
    dispatchEvent() {
      return false;
    },
  })) as typeof window.matchMedia;
}

afterEach(() => {
  window.matchMedia = originalMatchMedia;
});

function mountProbe() {
  const Probe = defineComponent({
    setup() {
      const isMobile = useIsMobile();
      const isCompact = useIsCompact();
      const scroll = useTableScroll();
      return () =>
        h(
          'pre',
          JSON.stringify({
            isMobile: isMobile.value,
            isCompact: isCompact.value,
            scroll: scroll.value ?? null,
          }),
        );
    },
  });
  return mount(Probe);
}

describe('responsive breakpoints', () => {
  it('exports the shared queries', () => {
    expect(MOBILE_QUERY).toBe('(max-width: 767px)');
    expect(COMPACT_QUERY).toBe('(max-width: 991px)');
  });

  it('treats phone width as mobile and compact, and enables table scroll', () => {
    installMatchMedia(
      (query) => query === MOBILE_QUERY || query === COMPACT_QUERY,
    );
    const wrapper = mountProbe();
    expect(JSON.parse(wrapper.text())).toEqual({
      isMobile: true,
      isCompact: true,
      scroll: { x: 'max-content' },
    });
  });

  it('treats tablet width as compact only', () => {
    installMatchMedia((query) => query === COMPACT_QUERY);
    const wrapper = mountProbe();
    expect(JSON.parse(wrapper.text())).toEqual({
      isMobile: false,
      isCompact: true,
      scroll: { x: 'max-content' },
    });
  });

  it('leaves desktop tables unconstrained', () => {
    installMatchMedia(() => false);
    const wrapper = mountProbe();
    expect(JSON.parse(wrapper.text())).toEqual({
      isMobile: false,
      isCompact: false,
      scroll: null,
    });
  });
});
