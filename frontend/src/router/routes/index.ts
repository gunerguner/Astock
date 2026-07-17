import type { RouteRecordNormalized } from 'vue-router';

type RouteModule = {
  default?: RouteRecordNormalized | RouteRecordNormalized[];
};

const modules = import.meta.glob('./modules/*.ts', {
  eager: true,
}) as Record<string, RouteModule>;

function formatModules(
  routeModules: Record<string, RouteModule>,
  result: RouteRecordNormalized[],
) {
  Object.keys(routeModules).forEach((key) => {
    const defaultModule = routeModules[key].default;
    if (!defaultModule) return;
    const moduleList = Array.isArray(defaultModule)
      ? [...defaultModule]
      : [defaultModule];
    result.push(...moduleList);
  });
  return result;
}

const appRoutes: RouteRecordNormalized[] = formatModules(modules, []);

export default appRoutes;
