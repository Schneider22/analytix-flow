/**
 * TypeScript types matching backend contracts in backend/app/schemas.py
 * for ProjectCreate and ProjectRead.
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
}

export interface ListProjectsParams {
  limit?: number;
  offset?: number;
}
