import { DEFAULT_LAYOUT } from '../base';
import { AppRouteRecordRaw } from '../types';

const MAIN: AppRouteRecordRaw = {
  path: '/',
  name: 'root',
  component: DEFAULT_LAYOUT,
  redirect: '/bull-market',
  meta: {
    hideInMenu: true,
    requiresAuth: false,
    order: 0,
  },
  children: [
    {
      path: 'bull-market',
      name: 'BullMarket',
      component: () => import('@/views/bull-market/index.vue'),
      meta: {
        locale: 'menu.bullMarket',
        requiresAuth: false,
        icon: 'icon-bar-chart',
        order: 1,
      },
    },
    {
      path: 'turnover-rank',
      name: 'TurnoverRank',
      component: () => import('@/views/turnover-rank/index.vue'),
      meta: {
        locale: 'menu.turnoverRank',
        requiresAuth: false,
        icon: 'icon-sort',
        order: 2,
      },
    },
  ],
};

export default MAIN;
