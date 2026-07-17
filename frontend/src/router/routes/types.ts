import { defineComponent, type Component as VueComponent } from 'vue';
import type { RouteMeta, NavigationGuard } from 'vue-router';

export type Component<T = unknown> =
  | ReturnType<typeof defineComponent>
  | VueComponent
  | (() => Promise<typeof import('*.vue')>)
  | (() => Promise<T>);

export interface AppRouteRecordRaw {
  path: string;
  name?: string | symbol;
  meta?: RouteMeta;
  redirect?: string;
  component: Component | string;
  children?: AppRouteRecordRaw[];
  alias?: string | string[];
  props?: Record<string, unknown> | boolean;
  beforeEnter?: NavigationGuard | NavigationGuard[];
  fullPath?: string;
}
