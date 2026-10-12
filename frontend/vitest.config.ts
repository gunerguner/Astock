import { resolve } from 'path';
import { defineConfig } from 'vitest/config';

// 前端测试配置:仅匹配 tests/ 目录(镜像 src/ 结构),不进入 src/ 模块内部
export default defineConfig({
  resolve: {
    alias: {
      '@': resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'happy-dom',
    include: ['tests/**/*.test.ts'],
    restoreMocks: true,
  },
});
