import { apiClient } from './client';
import { HealthResponse } from '../types/api';

/**
 * Check backend and database operational health.
 * Maps to GET /api/v1/health
 */
export async function getHealth(correlationId?: string): Promise<HealthResponse> {
  return apiClient.get<HealthResponse>('/health', { correlationId });
}
