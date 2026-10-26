import { apiClient } from './client';
import { DecisionCreate, DecisionRead } from '../types/projects';

/**
 * Fetch all decisions registered for a project, ordered by creation date descending.
 * Maps to GET /api/v1/projects/{project_id}/decisions
 */
export async function listDecisions(projectId: string): Promise<DecisionRead[]> {
  if (!projectId || !projectId.trim()) {
    throw new Error('El identificador del proyecto es requerido');
  }
  return apiClient.get<DecisionRead[]>(`/projects/${encodeURIComponent(projectId.trim())}/decisions`);
}

/**
 * Register a new business or technical decision for a project.
 * Validates backend contract rules:
 * - selected_option must be in options
 * - if status === 'decided', selected_option and decided_by are mandatory
 * - evidence arrays are defaulted to empty lists
 * Maps to POST /api/v1/projects/{project_id}/decisions
 */
export async function createDecision(
  projectId: string,
  payload: DecisionCreate
): Promise<DecisionRead> {
  if (!projectId || !projectId.trim()) {
    throw new Error('El identificador del proyecto es requerido');
  }
  if (!payload.decision_type || !payload.decision_type.trim()) {
    throw new Error('El tipo de decisión es obligatorio');
  }
  if (!payload.question || !payload.question.trim()) {
    throw new Error('La pregunta de decisión es obligatoria');
  }
  if (!payload.options || payload.options.length === 0) {
    throw new Error('Debes definir al menos una opción');
  }

  const cleanOptions = payload.options.map((opt) => opt.trim()).filter(Boolean);
  if (cleanOptions.length === 0) {
    throw new Error('Las opciones no pueden estar vacías');
  }

  const status = payload.status ?? 'pending';

  if (status === 'decided') {
    if (!payload.selected_option || !payload.selected_option.trim()) {
      throw new Error('Una decisión en estado decided requiere una opción seleccionada');
    }
    if (!cleanOptions.includes(payload.selected_option.trim())) {
      throw new Error('La opción seleccionada debe pertenecer a la lista de opciones');
    }
    if (!payload.decided_by || !payload.decided_by.trim()) {
      throw new Error('Una decisión en estado decided requiere indicar el responsable (decided_by)');
    }
  }

  const cleanPayload: DecisionCreate = {
    decision_type: payload.decision_type.trim(),
    question: payload.question.trim(),
    options: cleanOptions,
    selected_option: payload.selected_option?.trim() || null,
    rationale: payload.rationale?.trim() || null,
    evidence_artifact_ids: payload.evidence_artifact_ids ?? [],
    evidence_artifact_refs: payload.evidence_artifact_refs ?? [],
    status,
    decided_by: payload.decided_by?.trim() || null,
  };

  return apiClient.post<DecisionRead>(
    `/projects/${encodeURIComponent(projectId.trim())}/decisions`,
    cleanPayload
  );
}
