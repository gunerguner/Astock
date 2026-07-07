<template>
  <a-layout-footer class="footer">
    <div class="footer-links">
      <a
        v-for="link in footerLinks"
        :key="link.key"
        class="footer-link"
        :href="link.href"
        target="_blank"
        rel="noopener noreferrer"
      >
        <icon-github v-if="link.key === 'github'" />
        <span v-else>{{ link.title }}</span>
      </a>
    </div>
    <div class="footer-copyright">{{ copyright }}</div>
  </a-layout-footer>
</template>

<script lang="ts" setup>
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';

  const START_YEAR = 2020;
  const CURRENT_YEAR = new Date().getFullYear();

  const { t } = useI18n();

  const copyright = computed(() => {
    const range =
      CURRENT_YEAR > START_YEAR
        ? `${START_YEAR}-${CURRENT_YEAR}`
        : `${START_YEAR}`;
    return t('footer.copyright', { range });
  });

  const footerLinks = [
    {
      key: 'arco-design-pro-vue',
      title: 'Arco Design Pro Vue',
      href: 'https://pro.arco.design/',
    },
    {
      key: 'fastapi',
      title: 'FastAPI',
      href: 'https://fastapi.tiangolo.com/',
    },
    {
      key: 'github',
      title: 'GitHub',
      href: 'https://github.com/gunerguner/Astock',
    },
    {
      key: 'icp',
      title: '沪ICP备2020026170号',
      href: 'https://beian.miit.gov.cn/',
    },
  ];
</script>

<style lang="less" scoped>
  .footer {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 12px 24px;
    color: var(--color-text-3);
    font-size: var(--fs-caption);
    line-height: var(--lh-caption);
    text-align: center;
    background-color: var(--color-bg-2);
  }

  .footer-links {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: center;
    gap: 4px 0;
  }

  .footer-link {
    display: inline-flex;
    align-items: center;
    padding: 0 12px;
    color: var(--color-text-3);
    font-size: var(--fs-caption);
    line-height: var(--lh-caption);
    text-decoration: none;
    transition: color 0.2s;

    &:not(:last-child) {
      border-right: 1px solid var(--color-border);
    }

    &:hover {
      color: var(--brand-6);
    }

    :deep(svg) {
      font-size: 14px;
    }
  }

  .footer-copyright {
    color: var(--color-text-3);
    font-size: var(--fs-caption);
    line-height: var(--lh-caption);
  }
</style>
