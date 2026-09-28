import React from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import { Breadcrumb as CarbonBreadcrumb, BreadcrumbItem } from '@carbon/react';
import { buildBreadcrumbs, getRouteMetadata, ROUTES } from '@/config';
import { useBreadcrumbActions } from '@/contexts';
import { useAppSelector } from '@/hooks';
import { makeSelectProject } from '@/selectors/projectsSelectors';
import { makeSelectFlowName } from '@/selectors/flowSelectors';
import { PreloadLink } from '../PreloadLink';
import styles from './Breadcrumb.module.scss';

// Pages that are top-level roots — they own their own title and need no breadcrumb trail.
// Every other route is reachable from Projects, so its trail starts with "Projects /..."
const TOP_LEVEL_PAGES: string[] = [ROUTES.HOME, ROUTES.PROJECTS];

/**
 * Matches a flow-scoped path, e.g. `/flows/<uuid>` or `/flows/<uuid>/canvas`.
 * Capture group 1 is the flow_id.
 */
const FLOW_PATH_RE = /^\/flows\/([^/]+)/;

/**
 * Matches any flow sub-page path — anything under `/flows/<id>/…`.
 * On these pages the flow itself is a navigable parent, not the current page.
 */
const FLOW_SUBPAGE_RE = /^\/flows\/[^/]+\/.+/;

/**
 * Matches a project-scoped path, e.g. `/projects/<id>` or `/projects/<id>/runs`.
 * Capture group 1 is the project_id.
 */
const PROJECT_PATH_RE = /^\/projects\/([^/]+)/;

/**
 * Breadcrumb bar rendered in the shared layout row below the app header.
 *
 * Behaviour:
 * - Returns `null` on top-level pages (`/home`, `/projects`) unless custom `actions`
 *   have been injected via {@link useBreadcrumbActions}, in which case the bar is
 *   shown for the actions slot alone.
 * - Returns `null` when the trail is empty (e.g. an unknown/404 route).
 * - The **current page crumb is never rendered** — the page `<h1>` already names it.
 *   Only parent crumbs are shown, all as {@link PreloadLink} anchors.
 *   e.g. on ProjectDetail   → `Projects /`
 *        on FlowDetail       → `Projects / <project-name> /`
 *        on Canvas           → `Projects / <project-name> / <flow-name> /`
 * - For project-scoped paths: the project UUID crumb is replaced with the project name
 *   once it is available in the Redux store.
 * - For flow-scoped paths (`/flows/…`): `project_id` is read from the `?project_id=`
 *   query param and used to build the project breadcrumb; the flow name is resolved
 *   from the flow slice by `flow_id`.
 * - Custom actions (buttons, etc.) are rendered on the right side of the bar when present.
 */
export function Breadcrumb(): React.JSX.Element | null {
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const { actions } = useBreadcrumbActions();

  // ── Resolve IDs from path and query string ────────────────────────────────

  // For project-scoped paths (/projects/:project_id/…)
  const projectIdFromPath = PROJECT_PATH_RE.exec(location.pathname)?.[1] ?? null;

  // For flow-scoped paths (/flows/:flow_id/…), project_id comes from query string
  const flowId = FLOW_PATH_RE.exec(location.pathname)?.[1] ?? null;
  const projectIdFromQuery = flowId ? (searchParams.get('project_id') ?? null) : null;

  // The effective project ID — from path for project pages, from query for flow pages
  const effectiveProjectId = projectIdFromPath ?? projectIdFromQuery;

  // ── Store lookups ─────────────────────────────────────────────────────────
  const project = useAppSelector(makeSelectProject(effectiveProjectId));
  const flowName = useAppSelector(makeSelectFlowName(flowId));

  // ── Build breadcrumb trail ────────────────────────────────────────────────

  let breadcrumbs: Array<{ label: string; path: string }>;

  if (flowId) {
    // Flow-scoped path — build the trail manually from known parts
    // because buildBreadcrumbs() operates on the path only (no query string awareness).
    //
    // On a flow sub-page (canvas, run details, …) the flow itself is a navigable
    // parent crumb, so we always include it. On the FlowDetail page itself it
    // will be dropped by slice(0, -1) as the current-page crumb.
    const isFlowSubpage = FLOW_SUBPAGE_RE.test(location.pathname);
    const flowCrumbPath = `/flows/${flowId}?project_id=${effectiveProjectId ?? ''}`;

    breadcrumbs = [
      { label: 'Projects', path: ROUTES.PROJECTS },
      ...(effectiveProjectId && project?.name
        ? [{
            label: project.name,
            path: `/projects/${effectiveProjectId}`,
          }]
        : []),
      // Always include the flow crumb when on a sub-page (keeps it as a parent link).
      // On FlowDetail itself, include it so slice(0,-1) drops it as the current page.
      // Only render once the name is available — avoids flashing the raw flow UUID.
      ...(flowName
        ? [{
            label: flowName,
            path: flowCrumbPath,
          }]
        : []),
      // On sub-pages, add a crumb for the current page so the flow crumb is kept.
      // Use the route's meta title (e.g. "Canvas", "Run Details") rather than the raw segment.
      ...(isFlowSubpage
        ? [{
            label: getRouteMetadata(location.pathname)?.title ?? location.pathname.split('/').pop() ?? '',
            path: location.pathname,
          }]
        : []),
    ];
  } else {
    // Project-scoped or other path — use the standard buildBreadcrumbs() logic.
    // Filter out the project UUID crumb entirely until the name is available —
    // once the fetch resolves, project.name replaces the raw UUID segment.
    breadcrumbs = buildBreadcrumbs(location.pathname).flatMap((crumb) => {
      if (projectIdFromPath && crumb.path === `/projects/${projectIdFromPath}`) {
        return project ? [{ ...crumb, label: project.name }] : [];
      }
      return [crumb];
    });
  }

  // Drop the last crumb — the current page is named by its own <h1>.
  const parentCrumbs = breadcrumbs.slice(0, -1);

  // Suppress the bar on top-level pages unless custom actions are injected.
  if (TOP_LEVEL_PAGES.includes(location.pathname) && !actions) {
    return null;
  }

  // Also suppress when there are no parent crumbs and no actions (e.g. unknown route).
  if (parentCrumbs.length === 0 && !actions) {
    return null;
  }

  return (
    <div className={styles.container}>
      <CarbonBreadcrumb noTrailingSlash>
        {parentCrumbs.map((crumb) => (
          <BreadcrumbItem key={crumb.path}>
            <PreloadLink to={crumb.path}>{crumb.label}</PreloadLink>
          </BreadcrumbItem>
        ))}
      </CarbonBreadcrumb>
      {!!actions && (
        <div className={styles.actions}>{actions}</div>
      )}
    </div>
  );
}
