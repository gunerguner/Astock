import { DEFAULT_LAYOUT } from '../base';
import { AppRouteRecordRaw } from '../types';

const MAIN: AppRouteRecordRaw = {
  path: '/',
  name: 'root',
  component: DEFAULT_LAYOUT,
  redirect: '/bull-market',
  meta: {
    hideInMenu: true,
    order: 0,
  },
  children: [
    {
      path: 'bull-market',
      name: 'BullMarket',
      component: () => import('@/views/bull-market/index.vue'),
      meta: {
        locale: 'menu.bullMarket',
        order: 1,
      },
    },
    {
      path: 'turnover-rank',
      name: 'TurnoverRank',
      component: () => import('@/views/turnover-rank/index.vue'),
      meta: {
        locale: 'menu.turnoverRank',
        order: 2,
      },
    },
    {
      path: 'asset-price-levels',
      name: 'AssetPriceLevels',
      component: () => import('@/views/asset-price-levels/index.vue'),
      meta: {
        locale: 'menu.assetPriceLevels',
        order: 3,
      },
    },
    {
      path: 'market-overview',
      name: 'MarketOverview',
      component: () => import('@/views/market-overview/index.vue'),
      meta: {
        locale: 'menu.marketOverview',
        order: 4,
      },
    },
    {
      path: 'cn-macro-data',
      name: 'CnMacroData',
      component: () => import('@/views/cn-macro-data/index.vue'),
      meta: {
        locale: 'menu.cnMacroData',
        order: 5,
      },
    },
    {
      path: 'us-macro-data',
      name: 'UsMacroData',
      component: () => import('@/views/us-macro-data/index.vue'),
      meta: {
        locale: 'menu.usMacroData',
        order: 6,
      },
    },
  ],
};

export default MAIN;
