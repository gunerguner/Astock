import 'vue-router';

declare module 'vue-router' {
  interface RouteMeta {
    locale?: string;
    hideInMenu?: boolean;
    order?: number;
  }
}
