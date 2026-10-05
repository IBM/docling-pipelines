/**
 * Project Actions
 *
 * HTTP calls to BFF endpoints (not backend API directly).
 * These call the BFF server which proxies to the Python backend.
 */

import { type AxiosResponse } from 'axios';
import { log4js, logUtil } from '@/utils/logger';
import type {
  ProjectResponse,
  PaginatedProjectResponse,
  ProjectCreateRequest,
  ProjectUpdateRequest,
  ProjectPatchRequest,
} from '@/types';
import { apiClient } from '../client';

const logger = log4js.getLogger('project.actions');

const BFF_HEADERS = {
  'Accept': 'application/json',
  'X-Requested-With': 'XMLHttpRequest',
};

/**
 * Creates a new project via the BFF.
 *
 * @param body - Project creation payload (name, description, tags).
 * @returns Axios response containing the created {@link ProjectResponse}.
 * @throws Re-throws the Axios error if the BFF or backend returns an error status.
 *
 * @example
 * ```ts
 * const { data } = await createProject({ name: 'My Project', tags: ['finance'] });
 * console.log(data.project_id);
 * ```
 *
 * BFF endpoint  : POST /api/projects
 * Backend proxy : POST /api/v1/projects
 */
export const createProject = async (
  body: ProjectCreateRequest
): Promise<AxiosResponse<ProjectResponse>> => {
  const url = '/api/projects';

  try {
    const response = await apiClient.post<ProjectResponse>(url, body, { headers: BFF_HEADERS });

    logUtil.info({
      logger,
      message: 'Successfully created project',
      data: { projectId: response.data.project_id, name: response.data.name },
    });

    return response;

  } catch (error) {
    logUtil.error({
      logger,
      message: 'Failed to create project',
      data: error,
    });
    throw error;
  }
};

/**
 * Lists projects with optional pagination and filtering via the BFF.
 *
 * @param params - Optional query filters.
 * @param params.limit  - Maximum number of results to return (default 100 on the BFF).
 * @param params.offset - Zero-based offset for pagination.
 * @param params.name   - Filter by project name (substring match).
 * @param params.tags   - Filter by one or more tag strings.
 * @returns Axios response containing a {@link PaginatedProjectResponse}.
 * @throws Re-throws the Axios error if the BFF or backend returns an error status.
 *
 * @example
 * ```ts
 * const { data } = await getProjects({ limit: 20, offset: 0 });
 * console.log(data.total_count);
 * ```
 *
 * BFF endpoint  : GET /api/projects
 * Backend proxy : GET /api/v1/projects
 */
export const getProjects = async (params?: {
  limit?: number;
  offset?: number;
  name?: string;
  tags?: string[];
}): Promise<AxiosResponse<PaginatedProjectResponse>> => {
  const queryParams = new URLSearchParams();

  if (params?.limit !== undefined) { queryParams.append('limit', params.limit.toString()); }
  if (params?.offset !== undefined) { queryParams.append('offset', params.offset.toString()); }
  if (params?.name) { queryParams.append('name', params.name); }
  if (params?.tags) { params.tags.forEach((tag) => { queryParams.append('tags', tag); }); }

  const url = `/api/projects${queryParams.toString() ? `?${queryParams.toString()}` : ''}`;

  try {
    const response = await apiClient.get<PaginatedProjectResponse>(url, { headers: BFF_HEADERS });

    logUtil.info({
      logger,
      message: 'Successfully listed projects',
      data: { count: response.data.projects.length, total: response.data.total_count },
    });

    return response;

  } catch (error) {
    logUtil.error({
      logger,
      message: 'Failed to list projects',
      data: error,
    });
    throw error;
  }
};

/**
 * Retrieves a single project by its ID via the BFF.
 *
 * @param projectId - UUID of the project to fetch.
 * @returns Axios response containing the matching {@link ProjectResponse}.
 * @throws Re-throws the Axios error if the project is not found (404) or another error occurs.
 *
 * @example
 * ```ts
 * const { data } = await getProject('22b87e44-d3f1-4edb-b3e6-da937eeea07f');
 * console.log(data.name);
 * ```
 *
 * BFF endpoint  : GET /api/projects/:projectId
 * Backend proxy : GET /api/v1/projects/:projectId
 */
export const getProject = async (projectId: string): Promise<AxiosResponse<ProjectResponse>> => {
  const url = `/api/projects/${projectId}`;

  try {
    const response = await apiClient.get<ProjectResponse>(url, { headers: BFF_HEADERS });

    logUtil.info({
      logger,
      message: 'Successfully fetched project',
      data: { projectId: response.data.project_id, name: response.data.name },
    });

    return response;

  } catch (error) {
    logUtil.error({
      logger,
      message: 'Failed to fetch project',
      data: { projectId, error },
    });
    throw error;
  }
};

/**
 * Fully replaces a project (PUT) via the BFF.
 *
 * All mutable fields must be provided — omitted fields are cleared on the backend.
 * Use {@link patchProject} for partial updates.
 *
 * @param projectId - UUID of the project to replace.
 * @param body      - Full replacement payload (name, description, tags).
 * @returns Axios response containing the updated {@link ProjectResponse}.
 * @throws Re-throws the Axios error if the project is not found (404) or another error occurs.
 *
 * @example
 * ```ts
 * const { data } = await replaceProject(id, { name: 'Renamed', tags: [] });
 * console.log(data.modified_on);
 * ```
 *
 * BFF endpoint  : PUT /api/projects/:projectId
 * Backend proxy : PUT /api/v1/projects/:projectId
 */
export const replaceProject = async (
  projectId: string,
  body: ProjectUpdateRequest
): Promise<AxiosResponse<ProjectResponse>> => {
  const url = `/api/projects/${projectId}`;

  try {
    const response = await apiClient.put<ProjectResponse>(url, body, { headers: BFF_HEADERS });

    logUtil.info({
      logger,
      message: 'Successfully replaced project',
      data: { projectId: response.data.project_id, name: response.data.name },
    });

    return response;

  } catch (error) {
    logUtil.error({
      logger,
      message: 'Failed to replace project',
      data: { projectId, error },
    });
    throw error;
  }
};

/**
 * Partially updates a project (PATCH) via the BFF.
 *
 * Only the fields present in `updates` are changed; omitted fields are left unchanged.
 * Use {@link replaceProject} when a full replacement is required.
 *
 * @param projectId - UUID of the project to update.
 * @param updates   - Partial payload — any subset of name, description, tags.
 * @returns Axios response containing the updated {@link ProjectResponse}.
 * @throws Re-throws the Axios error if the project is not found (404) or another error occurs.
 *
 * @example
 * ```ts
 * const { data } = await patchProject(id, { tags: ['new-tag'] });
 * ```
 *
 * BFF endpoint  : PATCH /api/projects/:projectId
 * Backend proxy : PATCH /api/v1/projects/:projectId
 */
export const patchProject = async (
  projectId: string,
  updates: ProjectPatchRequest
): Promise<AxiosResponse<ProjectResponse>> => {
  const url = `/api/projects/${projectId}`;

  try {
    const response = await apiClient.patch<ProjectResponse>(url, updates, { headers: BFF_HEADERS });

    logUtil.info({
      logger,
      message: 'Successfully partially updated project',
      data: { projectId: response.data.project_id, name: response.data.name },
    });

    return response;

  } catch (error) {
    logUtil.error({
      logger,
      message: 'Failed to partially update project',
      data: { projectId, error },
    });
    throw error;
  }
};

/**
 * Deletes a project by ID via the BFF.
 *
 * This action is permanent and cannot be undone.
 *
 * @param projectId - UUID of the project to delete.
 * @returns Axios response with an empty body (204 No Content).
 * @throws Re-throws the Axios error if the project is not found (404) or another error occurs.
 *
 * @example
 * ```ts
 * await deleteProject('22b87e44-d3f1-4edb-b3e6-da937eeea07f');
 * ```
 *
 * BFF endpoint  : DELETE /api/projects/:projectId
 * Backend proxy : DELETE /api/v1/projects/:projectId
 */
export const deleteProject = async (projectId: string): Promise<AxiosResponse<void>> => {
  const url = `/api/projects/${projectId}`;

  try {
    const response = await apiClient.delete<void>(url, { headers: BFF_HEADERS });

    logUtil.info({
      logger,
      message: 'Successfully deleted project',
      data: { projectId },
    });

    return response;

  } catch (error) {
    logUtil.error({
      logger,
      message: 'Failed to delete project',
      data: { projectId, error },
    });
    throw error;
  }
};
