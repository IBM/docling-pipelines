/**
 * Hook for preloading route components on hover/focus
 * Improves perceived performance by loading components before navigation
 */

import { useCallback } from 'react';
import { routeConfig, flattenRoutes } from '@/config/routes.config';

interface PreloadCache {
  [key: string]: Promise<any>;
}

const preloadCache: PreloadCache = {};

/**
 * Preload a route component by path
 */
function preloadRoute(path: string): void {
  // Skip if already preloading or preloaded
  if (preloadCache[path]) {
    return;
  }

  const flatRoutes = flattenRoutes(routeConfig);
  const route = flatRoutes.find((r) => {
    const pattern = r.path.replace(/:[^/]+/g, '[^/]+');
    const regex = new RegExp(`^${pattern}$`);
    return regex.test(path);
  });

  if (route) {
    // Store the promise to prevent duplicate preloads
    preloadCache[path] = route.component();
  }
}

/**
 * Hook to get preload function
 */
export function useRoutePreload() {
  const preload = useCallback((path: string) => {
    preloadRoute(path);
  }, []);

  return { preload };
}

/**
 * Preload multiple routes at once
 */
export function preloadRoutes(paths: string[]): void {
  paths.forEach((path) => {
    preloadRoute(path);
  });
}

/**
 * Clear preload cache (useful for testing or memory management)
 */
export function clearPreloadCache(): void {
  Object.keys(preloadCache).forEach((key) => {
    delete preloadCache[key];
  });
}
