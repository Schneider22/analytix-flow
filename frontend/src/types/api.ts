/**
 * TypeScript definitions aligned with backend contracts in backend/app/schemas.py
 */

export interface HealthResponse {
  status: 'ok' | 'degraded' | string;
  database: 'ok' | 'unavailable' | string;
}

export interface ApiValidationErrorItem {
  loc?: (string | number)[];
  msg: string;
  type?: string;
}

export interface ApiErrorDetail {
  detail: string | ApiValidationErrorItem[];
}
