/**
 * Generation packaging analysis
 * 生成打包分析
 */
import type { PluginOption } from 'vite';
import { isReportMode } from '../utils';

export default async function configVisualizerPlugin(): Promise<PluginOption> {
  if (!isReportMode()) {
    return [];
  }
  // rollup-plugin-visualizer@7 为 ESM-only，需动态 import 避免 Vite 配置 CJS 加载失败
  const { visualizer } = await import('rollup-plugin-visualizer');
  return visualizer({
    filename: './node_modules/.cache/visualizer/stats.html',
    open: true,
    gzipSize: true,
    brotliSize: true,
  });
}
