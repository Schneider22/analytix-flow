import { apiClient } from './client';
import { ProjectCreate, ProjectRead, ListProjectsParams } from '../types/projects';

/**
 * Fetch a paginated list of projects from the backend.
 * Maps to GET /api/v1/projects
 */
export async function listProjects(params?: ListProjectsParams): Promise<ProjectRead[]> {
  return apiClient.get<ProjectRead[]>('/projects', {
    params: {
      limit: params?.limit ?? 100,
      offset: params?.offset ?? 0,
    },
  });
}

/**
 * Fetch a single project by its unique identifier.
 * Maps to GET /api/v1/projects/{project_id}
 */
export async function getProject(projectId: string): Promise<ProjectRead> {
  if (!projectId || !projectId.trim()) {
    throw new Error('El identificador del proyecto es requerido');
  }
  return apiClient.get<ProjectRead>(`/projects/${encodeURIComponent(projectId.trim())}`);
}

/**
 * Create a new analytical project with validated CRISP-DM business understanding parameters.
 * Maps to POST /api/v1/projects
 */
export async function createProject(payload: ProjectCreate): Promise<ProjectRead> {
  // Build a strict payload matching backend ProjectCreate without extra properties
  const cleanPayload: ProjectCreate = {
    company_name: payload.company_name.trim(),
    company_description: payload.company_description.trim(),
    business_need: payload.business_need.trim(),
    expected_objective: payload.expected_objective.trim(),
    business_rules: payload.business_rules ?? [],
    constraints: payload.constraints ?? [],
    success_criteria: payload.success_criteria,
    owner_id: payload.owner_id?.trim() || null,
    organization_id: payload.organization_id?.trim() || null,
  };

  return apiClient.post<ProjectRead>('/projects', cleanPayload);
}
