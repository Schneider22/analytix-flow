import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { IngestionPanel } from './IngestionPanel';
import * as ingestionApi from '../../api/ingestion';
import { ContextRead, DecisionRead, ProjectRead } from '../../types/projects';

describe('IngestionPanel', () => {
  const project: ProjectRead = {
    id: 'project-1',
    company_name: 'Empresa Demo',
    company_description: 'Descripción',
    business_need: 'Necesidad',
    expected_objective: 'Objetivo',
    business_rules: [],
    constraints: [],
    success_criteria: ['Criterio'],
    owner_id: 'owner-1',
    organization_id: null,
    status: 'active',
    current_phase: 'data_understanding',
    created_at: '2026-10-27T00:00:00Z',
    updated_at: '2026-10-27T00:00:00Z',
  };
  const snapshot: ContextRead = {
    id: 'context-1',
    project_id: 'project-1',
    version: 1,
    predecessor_id: null,
    context: {
      company_name: 'Empresa Demo',
      company_description: 'Descripción',
      business_need: 'Necesidad',
      expected_objective: 'Objetivo',
      business_rules: [],
      constraints: [],
      assumptions: [],
      success_criteria: ['Criterio'],
    },
    content_hash: `sha256:${'b'.repeat(64)}`,
    created_by: 'owner-1',
    created_at: '2026-10-27T00:00:00Z',
  };
  const decision: DecisionRead = {
    id: 'decision-1',
    project_id: 'project-1',
    decision_type: 'select_alternative',
    question: '¿Qué alternativa?',
    options: ['alternative-a'],
    selected_option: 'alternative-a',
    rationale: 'Adecuada',
    evidence_artifact_ids: [],
    evidence_artifact_refs: [],
    status: 'decided',
    decided_by: 'owner-1',
    decided_at: '2026-10-27T00:00:00Z',
    created_at: '2026-10-27T00:00:00Z',
  };
  const sourceArtifact: ingestionApi.ArtifactReference = {
    artifact_id: 'source-1',
    artifact_type: 'source',
    artifact_version: 'v1',
    version_number: 1,
    content_hash: `sha256:${'a'.repeat(64)}`,
    media_type: 'text/csv',
    layer: 'source',
  };
  const result: ingestionApi.M2IngestionResult = {
    project_id: 'project-1',
    execution_id: 'm2-execution-1',
    module_id: 'm2',
    contract_version: 'v1.0',
    context_snapshot_id: 'context-1',
    correlation_id: 'corr-1',
    status: 'succeeded',
    warnings: ['The profile contains quality warnings that should be reviewed before M3.'],
    errors: [],
    module_output: {
      bronze_dataset: {
        artifact_id: 'bronze-m2-execution-1',
        artifact_type: 'dataset.bronze',
        artifact_version: 'v1',
        version_number: 1,
        content_hash: `sha256:${'c'.repeat(64)}`,
        layer: 'bronze',
      },
      profile_report: {
        structures: ['table'],
        row_count: 3,
        column_count: 2,
        columns: [{ name: 'id', dtype: 'int64', missing_count: 0, unique_count: 3, null_ratio: 0 }],
        potential_identifiers: ['table.id'],
      },
      issues: [{ issue_id: 'duplicates-table', severity: 'warning', description: 'Duplicate rows detected.' }],
    },
  };

  beforeEach(() => vi.restoreAllMocks());

  it('blocks execution when the context or selected alternative is missing', () => {
    render(<IngestionPanel project={project} snapshots={[]} decisions={[]} />);

    expect(screen.getByText('Falta una instantánea de contexto.')).toBeInTheDocument();
    expect(screen.getByText('Falta una decisión select_alternative decidida.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Cargar y perfilar/i })).toBeDisabled();
  });

  it('blocks file loading for archived projects', () => {
    render(<IngestionPanel project={{ ...project, status: 'archived' }} snapshots={[snapshot]} decisions={[decision]} />);

    expect(screen.getByText(/carga y ejecución están bloqueadas/i)).toBeInTheDocument();
    expect(screen.getByLabelText('Archivo de datos')).toBeDisabled();
    expect(screen.getByRole('button', { name: /Cargar y perfilar/i })).toBeDisabled();
  });

  it('uploads a CSV, executes M2, and renders the returned profile and Bronze reference', async () => {
    const user = userEvent.setup();
    const uploadSpy = vi.spyOn(ingestionApi, 'uploadSourceArtifact').mockResolvedValue(sourceArtifact);
    const runSpy = vi.spyOn(ingestionApi, 'runM2').mockResolvedValue(result);
    render(<IngestionPanel project={project} snapshots={[snapshot]} decisions={[decision]} />);

    const file = new File(['id,value\n1,10\n2,20\n'], 'orders.csv', { type: 'text/csv' });
    await user.upload(screen.getByLabelText('Archivo de datos'), file);
    await user.click(screen.getByRole('button', { name: /Cargar y perfilar/i }));

    await waitFor(() => expect(screen.getByTestId('ingestion-result')).toBeInTheDocument());
    expect(uploadSpy).toHaveBeenCalledWith('project-1', file, 'csv');
    expect(runSpy).toHaveBeenCalledWith('project-1', expect.objectContaining({
      contextSnapshotId: 'context-1',
      selectedAlternativeId: 'alternative-a',
      sourceArtifact,
      format: 'csv',
    }));
    expect(screen.getByText('Filas').parentElement).toHaveTextContent('3');
    expect(screen.getByTestId('bronze-reference')).toHaveTextContent('bronze-m2-execution-1');
    expect(screen.getByText(/Duplicate rows detected/)).toBeInTheDocument();
  });

  it('keeps the source artifact for an M2 retry after an execution error', async () => {
    const user = userEvent.setup();
    vi.spyOn(ingestionApi, 'uploadSourceArtifact').mockResolvedValue(sourceArtifact);
    const runSpy = vi.spyOn(ingestionApi, 'runM2')
      .mockRejectedValueOnce(new Error('M2 unavailable'))
      .mockResolvedValueOnce(result);
    render(<IngestionPanel project={project} snapshots={[snapshot]} decisions={[decision]} />);

    const file = new File(['id,value\n1,10\n'], 'orders.csv', { type: 'text/csv' });
    await user.upload(screen.getByLabelText('Archivo de datos'), file);
    await user.click(screen.getByRole('button', { name: /Cargar y perfilar/i }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('M2 unavailable'));

    await user.click(screen.getByRole('button', { name: /Reintentar M2/i }));
    await waitFor(() => expect(screen.getByTestId('ingestion-result')).toBeInTheDocument());
    expect(runSpy).toHaveBeenCalledTimes(2);
  });
});
