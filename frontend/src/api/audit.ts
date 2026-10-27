import { apiClient } from './client';
import { AuditEventRead } from '../types/projects';

/**
 * Fetch all audit events for a project from the immutable audit trail.
 * Maps to GET /api/v1/projects/{project_id}/audit
 */
export async function listAuditEvents(projectId: string): Promise<AuditEventRead[]> {
  if (!projectId || !projectId.trim()) {
    throw new Error('projectId es obligatorio para consultar la pista de auditoría');
  }
  return apiClient.get<AuditEventRead[]>(`/projects/${encodeURIComponent(projectId.trim())}/audit`);
}
