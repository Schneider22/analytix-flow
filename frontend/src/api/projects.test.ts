import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { listProjects, getProject, createProject } from './projects';
import { ProjectCreate, ProjectRead } from '../types/projects';
import { ApiError } from './client';

describe('Projects API Client', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  const mockProject: ProjectRead = {
    id: 'proj-uuid-123',
    company_name: 'TelcoGlobal Synthetic Services',
    company_description: 'Synthetic enterprise provider.',
    business_need: 'Churn reduction and retention prioritization.',
    expected_objective: 'Build a supervised classification model.',
    business_rules: ['Strictly isolate subscriber records.'],
    constraints: ['Local execution only.'],
    success_criteria: ['Holdout F1-score >= 0.60', 'Unbroken cryptographic lineage'],
    owner_id: 'test-architect',
    organization_id: null,
    status: 'draft',
    current_phase: 'business_understanding',
    created_at: '2026-10-26T12:00:00Z',
    updated_at: '2026-10-26T12:00:00Z',
  };

  it('listProjects sends GET /projects with default pagination params', async () => {
    let capturedUrl = '';
    globalThis.fetch = vi.fn().mockImplementation((url) => {
      capturedUrl = String(url);
      return Promise.resolve(
        new Response(JSON.stringify([mockProject]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    const result = await listProjects();
    expect(result).toEqual([mockProject]);
    expect(capturedUrl).toContain('/api/v1/projects?limit=100&offset=0');
  });

  it('listProjects respects custom limit and offset', async () => {
    let capturedUrl = '';
    globalThis.fetch = vi.fn().mockImplementation((url) => {
      capturedUrl = String(url);
      return Promise.resolve(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    await listProjects({ limit: 10, offset: 20 });
    expect(capturedUrl).toContain('/api/v1/projects?limit=10&offset=20');
  });

  it('getProject fetches single project by id', async () => {
    let capturedUrl = '';
    globalThis.fetch = vi.fn().mockImplementation((url) => {
      capturedUrl = String(url);
      return Promise.resolve(
        new Response(JSON.stringify(mockProject), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    const result = await getProject('proj-uuid-123');
    expect(result).toEqual(mockProject);
    expect(capturedUrl).toContain('/api/v1/projects/proj-uuid-123');
  });

  it('getProject throws error if projectId is blank', async () => {
    await expect(getProject('   ')).rejects.toThrowError(/identificador del proyecto es requerido/);
  });

  it('createProject sends POST /projects with cleaned payload', async () => {
    let capturedBody = '';
    globalThis.fetch = vi.fn().mockImplementation((_url, init) => {
      capturedBody = init?.body as string;
      return Promise.resolve(
        new Response(JSON.stringify(mockProject), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    const payload: ProjectCreate = {
      company_name: '  TelcoGlobal Synthetic Services  ',
      company_description: '  Synthetic enterprise provider.  ',
      business_need: '  Churn reduction.  ',
      expected_objective: '  Supervised model.  ',
      success_criteria: ['Holdout F1 >= 0.60'],
      business_rules: ['Rule 1'],
      constraints: ['Constraint 1'],
      owner_id: '  lead-architect  ',
    };

    const result = await createProject(payload);
    expect(result).toEqual(mockProject);

    const parsed = JSON.parse(capturedBody);
    expect(parsed.company_name).toBe('TelcoGlobal Synthetic Services');
    expect(parsed.owner_id).toBe('lead-architect');
    expect(parsed.organization_id).toBeNull();
  });

  it('createProject propagates ApiError when backend returns 422', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Company name required' }), {
        status: 422,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    const payload: ProjectCreate = {
      company_name: '',
      company_description: 'Desc',
      business_need: 'Need',
      expected_objective: 'Obj',
      success_criteria: ['Crit 1'],
    };

    await expect(createProject(payload)).rejects.toThrowError(ApiError);
  });
});
