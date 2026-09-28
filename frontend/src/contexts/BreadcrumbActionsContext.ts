import { createContext, useContext, type ReactNode } from 'react';

/** A single breadcrumb item: a label and an optional navigation path. */
export interface BreadcrumbItem {
  label: string;
  /** When provided the crumb is rendered as a link. Omit for the current page. */
  path?: string;
}

/**
 * Value shape of the breadcrumb actions context.
 *
 * Allows any page to inject arbitrary React content (e.g. action buttons)
 * into the right side of the breadcrumb bar without prop-drilling.
 */
interface BreadcrumbActionsContextValue {
  /** Content to render on the right side of the breadcrumb bar. `null` means nothing. */
  actions: ReactNode;
  /** Replaces the current breadcrumb actions content. Pass `null` to clear. */
  setActions: (actions: ReactNode) => void;
}

export const BreadcrumbActionsContext = createContext<BreadcrumbActionsContextValue>({
  actions: null,
  setActions: () => {},
});

/**
 * Returns the breadcrumb actions context value.
 *
 * Use `setActions` to push buttons or other content into the breadcrumb bar's
 * right slot. Clear on component unmount.
 */
export function useBreadcrumbActions(): BreadcrumbActionsContextValue {
  return useContext(BreadcrumbActionsContext);
}
