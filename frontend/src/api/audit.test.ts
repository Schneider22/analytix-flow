import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { listAuditEvents } from './audit';
import { AuditEventRead } from '../types/projects';
import { ApiError } from './client';

describe('Audit API Client', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  const mockAuditEvents: AuditEventRead[] = [
    {
      id: 'audit-event-1',
      project_id: 'proj-123',
      actor_type: 'user',
      actor_id: 'lead-architect',
      action: 'project.created',
      entity_type: 'project',
      entity_id: 'proj-123',
      module_id: null,
      input_hash: null,
      output_hash: null,
      correlation_id: 'corr-001',
      metadata: { company_name: 'Telco Global' },
      created_at: '2026-10-26T12:00:00Z',
    },
    {
      id: 'audit-event-2',
      project_id: 'proj-123',
      actor_type: 'user',
      actor_id: 'lead-architect',
      action: 'context.snapshot.created',
      entity_type: 'project_context_snapshot',
      entity_id: 'snap-001',
      module_id: null,
      input_hash: 'sha256:abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234',
      output_hash: 'sha256:abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234',
      correlation_id: 'corr-002',
      metadata: { version: 1, predecessor_id: null },
      created_at: '2026-10-26T12:05:00Z',
    },
  ];

  it('listAuditEvents fetches audit trail from GET /projects/{id}/audit', async () => {
    let capturedUrl = '';
    globalThis.fetch = vi.fn().mockImplementation((url) => {
      capturedUrl = String(url);
      return Promise.resolve(
        new Response(JSON.stringify(mockAuditEvents), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    const result = await listAuditEvents('proj-123');
    expect(result).toEqual(mockAuditEvents);
    expect(capturedUrl).toContain('/api/v1/projects/proj-123/audit');
  });

  it('listAuditEvents throws error when projectId is empty or whitespace', async () => {
    await expect(listAuditEvents('')).rejects.toThrowError(/projectId es obligatorio/);
    await expect(listAuditEvents('   ')).rejects.toThrowError(/projectId es obligatorio/);
  });

  it('listAuditEvents propagates ApiError when endpoint returns 404', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Project not found' }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    await expect(listAuditEvents('proj-missing')).rejects.toThrowError(ApiError);
  });
});
