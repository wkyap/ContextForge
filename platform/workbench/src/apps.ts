import {
  appMeta as careerforgeMeta,
  navSection as careerforgeNav,
  appRoutes as careerforgeRoutes,
  type AppRouteDef,
} from "@apps/careerforge/ui/routes";

export interface AppNavItem {
  to: string;
  label: string;
}

export interface AppNavSection {
  title: string;
  items: AppNavItem[];
}

export interface MountedApp {
  id: string;
  title: string;
  nav: AppNavSection;
  routes: AppRouteDef[];
}

export const mountedApps: MountedApp[] = [
  {
    id: careerforgeMeta.id,
    title: careerforgeMeta.title,
    nav: careerforgeNav,
    routes: careerforgeRoutes,
  },
];
