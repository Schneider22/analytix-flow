/**
 * TypeScript types matching backend contracts in backend/app/schemas.py
 * for Projects, Context Snapshots and Decisions.
 */

export interface ProjectCreate {
  company_name: string;
  company_description: string;
  business_need: string;
  expected_objective: string;
  business_rules?: string[];
  constraints?: string[];
  success_criteria: string[];
  owner_id?: string | null;
  organization_id?: string | null;
}

export interface ProjectRead {
  id: string;
  company_name: string;
  company_description: string;
  business_need: string;
  expected_objective: string;
  business_rules: string[];
  constraints: string[];
  success_criteria: string[];
  owner_id: string | null;
  organization_id: string | null;
  status: string;
  current_phase: string;
  created_at: string;
  updated_at: string;
  archived_at?: string | null;
  archived_from_status?: string | null;
}

export type ProjectArchiveFilter = 'exclude' | 'only' | 'include';

export interface ListProjectsParams {
  limit?: number;
  offset?: number;
  archived?: ProjectArchiveFilter;
}

export interface ProjectArchiveRequest {
  actor_id: string;
  reason: string;
}

export interface ProjectRestoreRequest {
  actor_id: string;
  reason?: string;
}

export interface ContextPayload {
  company_name: string;
  company_description: string;
  business_need: string;
  expected_objective: string;
  business_rules?: string[];
  constraints?: string[];
  assumptions?: string[];
  success_criteria: string[];
}

export interface ContextCreate {
  context: ContextPayload;
  created_by: string;
}

export interface ContextRead {
  id: string;
  project_id: string;
  version: number;
  predecessor_id: string | null;
  context: ContextPayload;
  content_hash: string;
  created_by: string;
  created_at: string;
}

export interface ArtifactReferenceInput {
  artifact_id: string;
  artifact_version: string;
}

export type DecisionStatus = 'pending' | 'decided' | 'rejected';

export interface DecisionCreate {
  decision_type: string;
  question: string;
  options: string[];
  selected_option?: string | null;
  rationale?: string | null;
  evidence_artifact_ids?: string[];
  evidence_artifact_refs?: ArtifactReferenceInput[];
  status?: DecisionStatus;
  decided_by?: string | null;
}

export interface DecisionRead {
  id: string;
  project_id: string;
  decision_type: string;
  question: string;
  options: string[];
  selected_option: string | null;
  rationale: string | null;
  evidence_artifact_ids: string[];
  evidence_artifact_refs: ArtifactReferenceInput[];
  status: DecisionStatus;
  decided_by: string | null;
  decided_at: string | null;
  created_at: string;
}

export interface AuditEventRead {
  id: string;
  project_id: string;
  actor_type: string;
  actor_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string;
  module_id: string | null;
  input_hash: string | null;
  output_hash: string | null;
  correlation_id: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface AlternativeComparison {
  id: string;
  name: string;
  approach: string;
  suitability: string;
  data_requirements: string;
  estimated_complexity: 'Baja' | 'Media' | 'Alta';
  risks_and_limitations: string;
  empirical_evidence_level: 'Alto' | 'Medio' | 'Preliminar';
}
