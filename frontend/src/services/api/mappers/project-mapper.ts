/**
 * @fileoverview Mapper between the Projects API wire types and the internal domain model.
 *
 * This is the **only** place in the codebase that knows about `ProjectResponse` field names.
 * All components, slices, and selectors work with {@link Project} exclusively.
 *
 * If the backend renames a field (e.g. `project_id` → `id`), only this file changes.
 */

import type {
  Project,
  ProjectResponse,
  ProjectCreateRequest,
  ProjectUpdateRequest,
  CreateProjectFormValues,
} from '@/types';

/**
 * Converts a raw `ProjectResponse` (API wire shape) into the internal {@link Project}
 * domain model used throughout the application.
 *
 * @param r - The raw response object from `GET /api/projects` or `POST /api/projects`.
 * @returns A {@link Project} with camelCase field names.
 */
export function fromResponse(r: ProjectResponse): Project {
  return {
    id: r.project_id,
    name: r.name,
    description: r.description,
    tags: r.tags,
    flowCount: r.flow_count,
    createdOn: r.created_on,
    modifiedOn: r.modified_on,
    createdBy: r.created_by,
    modifiedBy: r.modified_by,
  };
}

/**
 * Converts {@link CreateProjectFormValues} (from the Create Project tearsheet)
 * into a {@link ProjectCreateRequest} body for `POST /api/projects`.
 *
 * @param values - The validated form values from step 1 of the tearsheet.
 * @returns A request body ready to send to the BFF.
 */
export function toCreateRequest(values: CreateProjectFormValues): ProjectCreateRequest {
  return {
    name: values.name,
    description: values.description || null,
    tags: values.tags,
  };
}

/**
 * Converts a partial update shape (from {@link EditProjectModal}) into a
 * {@link ProjectUpdateRequest} body for `PUT /api/projects/:id`.
 *
 * @param updates - The edited name, description, and tags from the modal.
 * @returns A request body ready to send to the BFF.
 */
export function toUpdateRequest(
  updates: { name: string; description: string; tags: string[] }
): ProjectUpdateRequest {
  return {
    name: updates.name,
    description: updates.description || null,
    tags: updates.tags,
  };
}
