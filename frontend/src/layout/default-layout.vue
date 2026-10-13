<template>
  <a-layout class="layout">
    <div class="layout-navbar">
      <NavBar />
    </div>
    <a-layout class="layout-content" :style="paddingStyle">
      <a-layout-content>
        <PageLayout />
      </a-layout-content>
      <Footer />
    </a-layout>
  </a-layout>
</template>

<script lang="ts" setup>
  import NavBar from '@/components/navbar/index.vue';
  import Footer from '@/components/footer/index.vue';
  import PageLayout from './page-layout.vue';

  const paddingStyle = { paddingTop: 'var(--navbar-height)' };
</script>

<style scoped lang="less">
  @nav-size-height: var(--navbar-height);

  .layout {
    width: 100%;
    height: 100%;
  }

  .layout-navbar {
    position: fixed;
    top: 0;
    left: 0;
    z-index: 100;
    width: 100%;
    height: @nav-size-height;
  }

  .layout-content {
    min-height: 100vh;
    overflow-y: hidden;
    background-color: var(--color-bg-1);
  }
</style>
