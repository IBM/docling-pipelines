import React, { useContext } from 'react';

/**
 * Holds a ref to the DOM element rendered by the root Carbon `<Theme>` wrapper
 * in `App.tsx`.
 *
 * The `@carbon/ibm-products` `Tearsheet` component renders via a React portal
 * that defaults to `document.body`.  Because `document.body` sits outside the
 * `<Theme>` wrapper div, the tearsheet loses all Carbon CSS custom-property
 * overrides (`--cds-layer-01`, `--cds-background`, etc.) and always renders
 * with light-theme fallback values.
 *
 * By passing this element as `portalTarget`, every tearsheet portal is appended
 * inside the theme-class div so CSS variable inheritance works correctly for
 * both light and dark modes.
 */
export const ThemeElementContext = React.createContext<HTMLElement | null>(null);

/**
 * Returns the DOM element that carries the active Carbon theme class.
 * Falls back to `document.body` when called outside `ThemeElementContext.Provider`
 * (e.g. in tests or storybook).
 */
export function useThemeElement(): HTMLElement {
  return useContext(ThemeElementContext) ?? document.body;
}
