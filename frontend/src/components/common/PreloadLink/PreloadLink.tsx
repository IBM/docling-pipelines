import React from 'react';
import { Link, type LinkProps } from 'react-router-dom';
import { useRoutePreload } from '@/hooks';

/**
 * Props for {@link PreloadLink}.
 */
interface PreloadLinkProps extends LinkProps {
  /**
   * When `true` (default), triggers route preloading on hover and focus.
   * Set to `false` to render a plain React Router `Link` with no preload behaviour.
   */
  preload?: boolean;
}

/**
 * Drop-in replacement for React Router's `Link` that preloads the target route
 * component on pointer hover or keyboard focus.
 *
 * Preloading fires the lazy `import()` for the route's component bundle early,
 * so the component is ready in the module cache by the time the user clicks.
 * Duplicate preload calls for the same path are de-duplicated via a module-level cache.
 *
 * Pass `preload={false}` to opt out of preloading for a specific link.
 */
export function PreloadLink({
  to,
  preload = true,
  onMouseEnter,
  onFocus,
  children,
  ...props
}: PreloadLinkProps): React.JSX.Element {
  const { preload: preloadRoute } = useRoutePreload();

  const handleMouseEnter = (event: React.MouseEvent<HTMLAnchorElement>): void => {
    if (preload && typeof to === 'string') {
      preloadRoute(to);
    }
    onMouseEnter?.(event);
  };

  const handleFocus = (event: React.FocusEvent<HTMLAnchorElement>): void => {
    if (preload && typeof to === 'string') {
      preloadRoute(to);
    }
    onFocus?.(event);
  };

  return (
    <Link
      to={to}
      onMouseEnter={handleMouseEnter}
      onFocus={handleFocus}
      {...props}
    >
      {children}
    </Link>
  );
}
