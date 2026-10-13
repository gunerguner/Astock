import { createRouter, createWebHistory } from 'vue-router';

import appRoutes from './routes';
import { NOT_FOUND_ROUTE } from './routes/base';

const router = createRouter({
  history: createWebHistory(),
  routes: [...appRoutes, NOT_FOUND_ROUTE],
  scrollBehavior() {
    return { top: 0 };
  },
});

export default router;
