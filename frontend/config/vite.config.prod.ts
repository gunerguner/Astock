import { mergeConfig } from 'vite';
import baseConfig from './vite.config.base';
import configVisualizerPlugin from './plugin/visualizer';
import configArcoResolverPlugin from './plugin/arcoResolver';

export default mergeConfig(
  {
    mode: 'production',
    plugins: [configVisualizerPlugin(), configArcoResolverPlugin()],
    build: {
      // Vite 6 默认拆包即可；静态 manualChunks(arco/vue) 会触发 Circular chunk 警告
      chunkSizeWarningLimit: 2000,
    },
  },
  baseConfig,
);
