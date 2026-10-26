import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { listContextSnapshots, createContextSnapshot } from './context';
import { ContextCreate, ContextRead } from '../types/projects';
import { ApiError } from './client';

describe('Context API Client', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  const mockSnapshot: ContextRead = {
    id: 'snap-uuid-1',
    project_id: 'proj-123',
    version: 1,
    predecessor_id: null,
    context: {
      company_name: 'Telco Global',
      company_description: 'Telco Provider',
      business_need: 'Churn reduction',
      expected_objective: 'Predict churn risk',
      business_rules: ['Rule 1'],
      constraints: ['Constraint 1'],
      assumptions: ['Hypothesis A'],
      success_criteria: ['F1 >= 0.65'],
    },
    content_hash: 'sha256:abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234',
    created_by: 'lead_ds',
    created_at: '2026-10-26T12:00:00Z',
  };

  it('listContextSnapshots fetches context history from GET /projects/{id}/context', async () => {
    let capturedUrl = '';
    globalThis.fetch = vi.fn().mockImplementation((url) => {
      capturedUrl = String(url);
      return Promise.resolve(
        new Response(JSON.stringify([mockSnapshot]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    const result = await listContextSnapshots('proj-123');
    expect(result).toEqual([mockSnapshot]);
    expect(capturedUrl).toContain('/api/v1/projects/proj-123/context');
  });

  it('createContextSnapshot sends exact nested structure {"context": {...}, "created_by": "..."}', async () => {
    let capturedBody = '';
    globalThis.fetch = vi.fn().mockImplementation((_url, init) => {
      capturedBody = init?.body as string;
      return Promise.resolve(
        new Response(JSON.stringify(mockSnapshot), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    const payload: ContextCreate = {
      context: {
        company_name: 'Telco Global',
        company_description: 'Telco Provider',
        business_need: 'Churn reduction',
        expected_objective: 'Predict churn risk',
        business_rules: ['Rule 1'],
        constraints: ['Constraint 1'],
        assumptions: ['Hypothesis A'],
        success_criteria: ['F1 >= 0.65'],
      },
      created_by: 'lead_ds',
    };

    const result = await createContextSnapshot('proj-123', payload);
    expect(result).toEqual(mockSnapshot);

    const parsed = JSON.parse(capturedBody);
    expect(parsed.context).toBeDefined();
    expect(parsed.context.company_name).toBe('Telco Global');
    expect(parsed.context.assumptions).toEqual(['Hypothesis A']);
    expect(parsed.created_by).toBe('lead_ds');
  });

  it('createContextSnapshot rejects when created_by is blank', async () => {
    const payload: ContextCreate = {
      context: {
        company_name: 'Telco Global',
        company_description: 'Desc',
        business_need: 'Need',
        expected_objective: 'Obj',
        success_criteria: ['Crit 1'],
      },
      created_by: '   ',
    };

    await expect(createContextSnapshot('proj-123', payload)).rejects.toThrowError(
      /created_by es obligatorio/
    );
  });

  it('createContextSnapshot propagates ApiError on 422', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Validation failed' }), {
        status: 422,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    const payload: ContextCreate = {
      context: {
        company_name: 'Telco Global',
        company_description: 'Desc',
        business_need: 'Need',
        expected_objective: 'Obj',
        success_criteria: ['Crit 1'],
      },
      created_by: 'lead_ds',
    };

    await expect(createContextSnapshot('proj-123', payload)).rejects.toThrowError(ApiError);
  });
});
