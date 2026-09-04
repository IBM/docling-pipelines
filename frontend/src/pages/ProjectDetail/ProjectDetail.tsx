import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { go } from '@/utils';
import { Tag } from '@carbon/react';
import { Add, ChevronUp, ChevronDown } from '@carbon/icons-react';
import { NoDataEmptyState } from '@carbon/ibm-products';
import { PageLayout } from '@/components';
import { CreateFlowTearsheet, FlowsTable } from '@/components/common';
import { buildFlowDefinition } from '@/lib/helpers';
import { createFlow, patchFlow, deleteFlow, getProjects, getFlowsByProjectId } from '@/services/api';
import * as projectMapper from '@/services/api/mappers/project-mapper';
import * as flowMapper from '@/services/api/mappers/flow-mapper';
import type { CreateFlowFormValues } from '@/types';
import { setProjects, setProject, setLoading, setError } from '@/slices/projectsSlice';
import { setFlows, setFlow, updateFlow, removeFlow, setLoading as setFlowsLoading, setError as setFlowsError } from '@/slices/flowSlice';
import {
  selectProjectsLoading,
  selectProjectsError,
  makeSelectProject,
  selectFlowsArray,
  selectFlowLoading,
} from '@/selectors';
import { useAppDispatch, useAppSelector, useTheme, useNotify } from '@/hooks';
import { useRecentlyVisited } from '@/hooks/useRecentlyVisited';
import { ROUTES, generateRoute } from '@/config';
import styles from './ProjectDetail.module.scss';

/**
 * Project detail page — rendered at `/projects/:projectId`.
 *
 * Layout (two-zone, full-bleed):
 * - **White header zone** — project name, description + meta, tags + collapse chevron.
 *   Rendered as soon as `project` resolves from the store, even while flows are
 *   still loading — the project fetch and the flows fetch are independent.
 * - **Grey content zone** — {@link FlowsTable}, which renders its own
 *   `DataTableSkeleton` (via its `isLoading` prop) whenever a flows fetch is
 *   in-flight (initial load or manual Refresh), or `NoDataEmptyState` once
 *   loaded with zero flows. This avoids a spinner flash, layout shift, and
 *   stale rows briefly showing during navigation between projects.
 *
 * Flows are stored in `state.flow.items` (mirroring how projects are stored in
 * `state.projects.items`). Navigating away and back re-uses the cached rows;
 * the Refresh button triggers a full re-fetch.
 */
export function ProjectDetail(): React.JSX.Element | null {
  // project_id in the URL is the raw UUID from the API (e.g. "abc-123").
  const { project_id: projectId } = useParams<{ project_id: string }>();
  const navigate = useNavigate();
  const { isDarkMode } = useTheme();
  const dispatch = useAppDispatch();
  const notify = useNotify();
  const { addEntry, removeEntry } = useRecentlyVisited();

  // ── Project from store ───────────────────────────────────────────────────
  const project = useAppSelector(makeSelectProject(projectId));
  const loading = useAppSelector(selectProjectsLoading);
  const error = useAppSelector(selectProjectsError);
  // ── Flows from store ─────────────────────────────────────────────────────
  const flows = useAppSelector(selectFlowsArray);
  const flowsLoading = useAppSelector(selectFlowLoading);

  const [collapsed, setCollapsed] = useState(false);
  const [createFlowOpen, setCreateFlowOpen] = useState(false);
  const [createFlowLoading, setCreateFlowLoading] = useState(false);
  const [createFlowError, setCreateFlowError] = useState<string | null>(null);

  // ── Bootstrap: fetch projects if this specific project isn't in the store ─
  // We cannot rely on `storePopulated` alone — the store may hold a different
  // page of results (e.g. the 5 fetched by ProjectsCard) that doesn't include
  // this project ID. Always fetch when the project is missing.
  useEffect(() => {
    if (project) { return; }         // already in store — nothing to do
    if (loading) { return; }         // fetch already in flight
    dispatch(setLoading(true));
    getProjects()
      .then((res) => {
        const projectsMap = Object.fromEntries(
          res.data.projects.map((p) => {
            const domain = projectMapper.fromResponse(p);
            return [domain.id, domain];
          })
        );
        dispatch(setProjects(projectsMap));
      })
      .catch(() => {
        dispatch(setError('Failed to load project. Please try again.'));
      })
      .finally(() => {
        dispatch(setLoading(false));
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  // ── Fetch flows for this project, write to store ─────────────────────────
  const fetchFlows = useCallback((projectId: string): void => {
    dispatch(setFlowsLoading(true));
    getFlowsByProjectId(projectId)
      .then((res) => {
        const flowsMap = Object.fromEntries(
          res.data.flows.map((f) => {
            const row = flowMapper.fromResponse(f);
            return [row.flow_id, row];
          })
        );
        dispatch(setFlows(flowsMap));
      })
      .catch(() => {
        dispatch(setFlowsError('Failed to load flows. Please try again.'));
      })
      .finally(() => {
        dispatch(setFlowsLoading(false));
      });
  }, [dispatch]);

  useEffect(() => {
    if (project?.id) { fetchFlows(project.id); }
  }, [project?.id, fetchFlows]);

  // Keep the project's flowCount in sync with the authoritative flows list
  // returned by fetchFlows — that list is always freshly re-fetched on mount,
  // including when navigating back from Canvas after creating/editing a flow
  // there. This corrects the header count in cases the optimistic increments
  // in handleFlowSubmit/handleDeleteFlow don't cover (e.g. flows created or
  // removed from elsewhere). No-ops once the count already matches.
  useEffect(() => {
    if (!project || flowsLoading) { return; }
    if (project.flowCount === flows.length) { return; }
    dispatch(setProject({
      projectId: project.id,
      project: { ...project, flowCount: flows.length },
    }));
  }, [project, flows.length, flowsLoading, dispatch]);

  // Record this project as recently visited once its name is available.
  // Runs only when the project ID changes — addEntry is stable (useCallback []).
  useEffect(() => {
    if (!project) { return; }
    addEntry({
      id: `project-${project.id}`,
      label: project.name,
      path: generateRoute.projectDetail(project.id),
      type: 'project',
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps -- project.name/.path intentionally omitted; re-recording on label change is unnecessary
  }, [project?.id, addEntry]);

  const hasFlows = flows.length > 0;

  // ── Handlers ─────────────────────────────────────────────────────────────
  const handleCreateFlow = (): void => {
    setCreateFlowError(null);
    setCreateFlowOpen(true);
  };

  const handleFlowTearsheetClose = (): void => {
    setCreateFlowError(null);
    setCreateFlowOpen(false);
  };

  const handleFlowSubmit = async (values: CreateFlowFormValues): Promise<void> => {
    setCreateFlowLoading(true);
    setCreateFlowError(null);
    try {
      const response = await createFlow(
        flowMapper.toCreateRequest(values, project?.id ?? '', buildFlowDefinition(values.name, values.description))
      );
      const newRow = flowMapper.fromResponse(response.data);
      dispatch(setFlow({ flowId: newRow.flow_id, flow: newRow }));
      setCreateFlowOpen(false);
      notify.success(`${values.name} created successfully.`);
      if (response.data.flow_id) {
        go(navigate, generateRoute.canvas(response.data.flow_id, project?.id ?? projectId ?? ''));
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'An unexpected error occurred.';
      setCreateFlowError(message);
      notify.error('Failed to create flow', { subtitle: message });
    } finally {
      setCreateFlowLoading(false);
    }
  };

  const handleOpenFlow = (flowId: string): void => {
    go(navigate, generateRoute.flowDetail(flowId, project?.id ?? projectId ?? ''));
  };

  const handleDeleteFlow = (flowId: string): Promise<void> => {
    const flowName = flows.find((f) => f.flow_id === flowId)?.name ?? 'Flow';
    return deleteFlow(flowId)
      .then((): void => {
        dispatch(removeFlow(flowId));
        notify.success(`${flowName} deleted successfully.`);
        // Decrement the project's flow count in the store so the header reflects
        // the deletion without a full re-fetch.
        if (project) {
          dispatch(setProject({
            projectId: project.id,
            project: { ...project, flowCount: Math.max(0, project.flowCount - 1) },
          }));
        }
      })
      .catch((err: unknown) => {
        notify.error(`${flowName} failed to delete.`);
        throw err;
      });
  };

  const handleEditFlow = (
    flowId: string,
    updates: { name: string; description: string; tags: string[] }
  ): Promise<void> =>
    patchFlow(flowId, flowMapper.toPatchRequest(updates))
      .then((): void => {
        dispatch(updateFlow({ flowId, updates: { name: updates.name, description: updates.description, tags: updates.tags } }));
        notify.success(`${updates.name} updated successfully.`);
      })
      .catch((err: unknown) => {
        notify.error('Failed to update flow');
        throw err;
      });

  const handleRefresh = (): void => {
    if (project?.id) { fetchFlows(project.id); }
  };

  // ── Loading / error / not-found guards ───────────────────────────────────
  // ── Redirect to error page once fetch settles without a result ───────────
  useEffect(() => {
    if (loading) { return; }
    if (project) { return; }
    if (projectId) { removeEntry(`project-${projectId}`); }
    if (error) {
      go(navigate, ROUTES.ERROR, { state: { message: error, statusCode: 500 }, replace: true });
    } else {
      go(navigate, ROUTES.ERROR, { state: { message: 'Project not found.', statusCode: 404 }, replace: true });
    }
  }, [loading, project, error, projectId, removeEntry, navigate]);

  // Nothing to render yet — project fetch is in flight or a redirect is about
  // to fire. No spinner here: this window is brief and the project header has
  // no natural skeleton shape, so returning null avoids adding a new flicker
  // of its own.
  if (!project) {
    return null;
  }

  const createdOn = new Date(project.createdOn).toLocaleDateString();
  const lastUpdated = new Date(project.modifiedOn).toLocaleDateString();

  return (
    <PageLayout fullBleed>
      <div className={styles.page}>

        {/* ── White project header ── */}
        <div className={styles.headerZone}>
          <h1 className={styles.projectName}>{project.name}</h1>

          {!collapsed && (
            <div className={styles.detailsRow}>
              <p className={styles.description}>{project.description ?? ''}</p>
              <div className={styles.meta}>
                <p className={styles.metaItem}>{'Created: '}<strong>{createdOn}</strong></p>
                <p className={styles.metaItem}>{'Last updated: '}<strong>{lastUpdated}</strong></p>
                <p className={styles.metaItem}>{'Flows: '}<strong>{project.flowCount}</strong></p>
              </div>
            </div>
          )}

          <div className={styles.collapseBar}>
            <div className={styles.tagsRow}>
              {project.tags.map((tag) => (
                <Tag key={tag} type="blue" size="sm">{tag}</Tag>
              ))}
            </div>
            <button
              type="button"
              aria-label={collapsed ? 'Expand project details' : 'Collapse project details'}
              onClick={() => { setCollapsed((c) => !c); }}
            >
              {collapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
            </button>
          </div>
        </div>

        {/* ── Grey content zone ── */}
        <div className={styles.contentZone}>
          {hasFlows || flowsLoading ? (
            <FlowsTable
              rows={flows}
              isLoading={flowsLoading}
              onNewFlow={handleCreateFlow}
              onOpenFlow={handleOpenFlow}
              onRefresh={handleRefresh}
              onEditFlow={handleEditFlow}
              onDeleteFlow={handleDeleteFlow}
            />
          ) : (
            <NoDataEmptyState
              className={styles.emptyState}
              illustrationTheme={isDarkMode ? 'dark' : 'light'}
              illustrationPosition="top"
              size="sm"
              title="No flows created"
              action={{
                text: 'Create flow',
                onClick: handleCreateFlow,
                renderIcon: Add,
                kind: 'tertiary',
              }}
            />
          )}
        </div>

      </div>

      <CreateFlowTearsheet
        open={createFlowOpen}
        onClose={handleFlowTearsheetClose}
        onSubmit={(values) => { void handleFlowSubmit(values); }}
        isLoading={createFlowLoading}
        error={createFlowError}
        existingNames={flows.map((f) => f.name)}
      />

    </PageLayout>
  );
}
