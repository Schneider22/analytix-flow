import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { listDecisions, createDecision } from './decisions';
import { DecisionCreate, DecisionRead } from '../types/projects';
import { ApiError } from './client';

describe('Decisions API Client', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  const mockDecision: DecisionRead = {
    id: 'dec-1',
    project_id: 'proj-123',
    decision_type: 'select_alternative',
    question: '¿Qué técnica analítica utilizar?',
    options: ['supervised_tabular_classification', 'heuristic_rule_engine'],
    selected_option: 'supervised_tabular_classification',
    rationale: 'Datos etiquetados disponibles',
    evidence_artifact_ids: [],
    evidence_artifact_refs: [],
    status: 'decided',
    decided_by: 'lead_ds',
    decided_at: '2026-10-26T12:00:00Z',
    created_at: '2026-10-26T12:00:00Z',
  };

  it('listDecisions fetches decision list from GET /projects/{id}/decisions', async () => {
    let capturedUrl = '';
    globalThis.fetch = vi.fn().mockImplementation((url) => {
      capturedUrl = String(url);
      return Promise.resolve(
        new Response(JSON.stringify([mockDecision]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    const result = await listDecisions('proj-123');
    expect(result).toEqual([mockDecision]);
    expect(capturedUrl).toContain('/api/v1/projects/proj-123/decisions');
  });

  it('createDecision creates decision in pending status without selected_option', async () => {
    let capturedBody = '';
    globalThis.fetch = vi.fn().mockImplementation((_url, init) => {
      capturedBody = init?.body as string;
      return Promise.resolve(
        new Response(JSON.stringify(mockDecision), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    const payload: DecisionCreate = {
      decision_type: 'select_alternative',
      question: '¿Qué técnica analítica utilizar?',
      options: ['opcion-a', 'opcion-b'],
      status: 'pending',
    };

    const result = await createDecision('proj-123', payload);
    expect(result).toEqual(mockDecision);

    const parsed = JSON.parse(capturedBody);
    expect(parsed.status).toBe('pending');
    expect(parsed.selected_option).toBeNull();
    expect(parsed.evidence_artifact_refs).toEqual([]);
  });

  it('createDecision creates decided decision with selected_option and decided_by', async () => {
    let capturedBody = '';
    globalThis.fetch = vi.fn().mockImplementation((_url, init) => {
      capturedBody = init?.body as string;
      return Promise.resolve(
        new Response(JSON.stringify(mockDecision), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        })
      );
    });

    const payload: DecisionCreate = {
      decision_type: 'select_alternative',
      question: '¿Qué técnica analítica utilizar?',
      options: ['supervised_tabular_classification', 'heuristic_rule_engine'],
      selected_option: 'supervised_tabular_classification',
      status: 'decided',
      decided_by: 'lead_ds',
      rationale: 'Datos etiquetados disponibles',
    };

    const result = await createDecision('proj-123', payload);
    expect(result).toEqual(mockDecision);

    const parsed = JSON.parse(capturedBody);
    expect(parsed.status).toBe('decided');
    expect(parsed.selected_option).toBe('supervised_tabular_classification');
    expect(parsed.decided_by).toBe('lead_ds');
  });

  it('createDecision rejects when status is decided but selected_option is not in options', async () => {
    const payload: DecisionCreate = {
      decision_type: 'select_alternative',
      question: 'Pregunta',
      options: ['opcion-a', 'opcion-b'],
      selected_option: 'opcion-inexistente',
      status: 'decided',
      decided_by: 'lead_ds',
    };

    await expect(createDecision('proj-123', payload)).rejects.toThrowError(
      /La opción seleccionada debe pertenecer a la lista de opciones/
    );
  });

  it('createDecision rejects when status is decided but decided_by is missing', async () => {
    const payload: DecisionCreate = {
      decision_type: 'select_alternative',
      question: 'Pregunta',
      options: ['opcion-a', 'opcion-b'],
      selected_option: 'opcion-a',
      status: 'decided',
      decided_by: '',
    };

    await expect(createDecision('proj-123', payload)).rejects.toThrowError(
      /requiere indicar el responsable/
    );
  });

  it('createDecision propagates ApiError on 422', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Validation failed' }), {
        status: 422,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    const payload: DecisionCreate = {
      decision_type: 'select_alternative',
      question: 'Pregunta',
      options: ['opcion-a', 'opcion-b'],
    };

    await expect(createDecision('proj-123', payload)).rejects.toThrowError(ApiError);
  });
});
