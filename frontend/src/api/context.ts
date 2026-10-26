import { apiClient } from './client';
import { ContextCreate, ContextRead } from '../types/projects';

/**
 * Fetch all context snapshots for a project, ordered by version ascending.
 * Maps to GET /api/v1/projects/{project_id}/context
 */
export async function listContextSnapshots(projectId: string): Promise<ContextRead[]> {
  if (!projectId || !projectId.trim()) {
    throw new Error('El identificador del proyecto es requerido');
  }
  return apiClient.get<ContextRead[]>(`/projects/${encodeURIComponent(projectId.trim())}/context`);
}

/**
 * Create a new immutable, append-only context snapshot for a project.
 * Enforces the exact structure {"context": {...}, "created_by": "..."} required by backend.
 * Maps to POST /api/v1/projects/{project_id}/context
 */
export async function createContextSnapshot(
  projectId: string,
  payload: ContextCreate
): Promise<ContextRead> {
  if (!projectId || !projectId.trim()) {
    throw new Error('El identificador del proyecto es requerido');
  }
  if (!payload.created_by || !payload.created_by.trim()) {
    throw new Error('El campo created_by es obligatorio');
  }

  const cleanPayload: ContextCreate = {
    context: {
      company_name: payload.context.company_name.trim(),
      company_description: payload.context.company_description.trim(),
      business_need: payload.context.business_need.trim(),
      expected_objective: payload.context.expected_objective.trim(),
      business_rules: payload.context.business_rules ?? [],
      constraints: payload.context.constraints ?? [],
      assumptions: payload.context.assumptions ?? [],
      success_criteria: payload.context.success_criteria,
    },
    created_by: payload.created_by.trim(),
  };

  return apiClient.post<ContextRead>(
    `/projects/${encodeURIComponent(projectId.trim())}/context`,
    cleanPayload
  );
}
