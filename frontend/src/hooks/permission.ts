import { RouteLocationNormalized, RouteRecordRaw } from 'vue-router';

export default function usePermission() {
  return {
    accessRouter(_route: RouteLocationNormalized | RouteRecordRaw) {
      return true;
    },
    findFirstPermissionRoute(_routers: any) {
      return null;
    },
  };
}
