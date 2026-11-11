import { resolve } from 'path';
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import vueJsx from '@vitejs/plugin-vue-jsx';
import configArcoStyleImportPlugin from './plugin/arcoStyleImport';

export default defineConfig({
  plugins: [vue(), vueJsx(), configArcoStyleImportPlugin()],
  resolve: {
    alias: [
      {
        find: '@',
        replacement: resolve(__dirname, '../src'),
      },
    ],
    extensions: ['.ts', '.js'],
  },
  define: {
    'process.env': {},
  },
  css: {
    preprocessorOptions: {
      less: {
        javascriptEnabled: true,
        // 项目内 less（含 SFC scoped style）自动注入断点变量，避免各页重复魔法数字
        additionalData: (content: string, filePath: string) => {
          if (
            filePath.includes('node_modules') ||
            filePath.endsWith('breakpoint.less')
          ) {
            return content;
          }
          return `@import "@/assets/style/breakpoint.less";\n${content}`;
        },
      },
    },
  },
});
