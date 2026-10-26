import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ContextTimeline } from './ContextTimeline';
import { ContextRead, ProjectRead } from '../../types/projects';

const mockProject: ProjectRead = {
  id: 'proj-12345678-abcd-ef01-2345-6789abcdef01',
  company_name: 'Telco Global Corp',
  company_description: 'Proveedor de servicios móviles',
  business_need: 'Reducir tasa de churn',
  expected_objective: 'Modelo predictivo',
  business_rules: ['Regla 1'],
  constraints: ['Restricción 1'],
  success_criteria: ['Criterio 1'],
  owner_id: 'lead-architect',
  organization_id: 'org-123',
  status: 'draft',
  current_phase: 'business_understanding',
  created_at: '2026-03-30T10:00:00Z',
  updated_at: '2026-03-30T10:00:00Z',
};

const mockSnapshots: ContextRead[] = [
  {
    id: 'ctx-v1',
    project_id: mockProject.id,
    version: 1,
    predecessor_id: null,
    content_hash: '11111111222233334444555566667777888899990000aaaabbbbccccddddeeee',
    context: {
      company_name: 'Telco Global Corp',
      company_description: 'Proveedor telecom v1',
      business_need: 'Reducir churn v1',
      expected_objective: 'AUC >= 0.80',
      business_rules: ['Regla v1'],
      constraints: ['Restricción v1'],
      assumptions: ['Hipótesis v1'],
      success_criteria: ['Criterio v1'],
    },
    created_by: 'alice',
    created_at: '2026-03-30T10:00:00Z',
  },
  {
    id: 'ctx-v2',
    project_id: mockProject.id,
    version: 2,
    predecessor_id: 'ctx-v1',
    content_hash: '2222222233334444555566667777888899990000aaaabbbbccccddddeeeeffff',
    context: {
      company_name: 'Telco Global Corp',
      company_description: 'Proveedor telecom v2',
      business_need: 'Reducir churn v2',
      expected_objective: 'AUC >= 0.85',
      business_rules: ['Regla v2'],
      constraints: ['Restricción v2'],
      assumptions: ['Hipótesis v2'],
      success_criteria: ['Criterio v2'],
    },
    created_by: 'bob',
    created_at: '2026-03-30T12:00:00Z',
  },
];

describe('ContextTimeline Component', () => {
  const onRetryMock = vi.fn();
  const onSnapshotCreatedMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state when isLoading is true', () => {
    render(
      <ContextTimeline
        project={mockProject}
        snapshots={[]}
        isLoading={true}
        error={null}
        onRetry={onRetryMock}
        onSnapshotCreated={onSnapshotCreatedMock}
      />
    );

    expect(screen.getByText(/Cargando historial de versiones de contexto/i)).toBeInTheDocument();
  });

  it('renders error state and handles retry click', async () => {
    const user = userEvent.setup();

    render(
      <ContextTimeline
        project={mockProject}
        snapshots={[]}
        isLoading={false}
        error="Error de conexión al cargar versiones"
        onRetry={onRetryMock}
        onSnapshotCreated={onSnapshotCreatedMock}
      />
    );

    expect(screen.getByText('Error al cargar las instantáneas de contexto')).toBeInTheDocument();
    expect(screen.getByText('Error de conexión al cargar versiones')).toBeInTheDocument();

    const retryBtn = screen.getByRole('button', { name: /Reintentar carga/i });
    await user.click(retryBtn);

    expect(onRetryMock).toHaveBeenCalledTimes(1);
  });

  it('renders empty state when there are no snapshots', () => {
    render(
      <ContextTimeline
        project={mockProject}
        snapshots={[]}
        isLoading={false}
        error={null}
        onRetry={onRetryMock}
        onSnapshotCreated={onSnapshotCreatedMock}
      />
    );

    expect(screen.getByText('Sin instantáneas registradas en el historial')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Crear Versión Inicial \(v1\)/i })).toBeInTheDocument();
  });

  it('renders snapshots in timeline with active badge on the latest version', () => {
    render(
      <ContextTimeline
        project={mockProject}
        snapshots={mockSnapshots}
        isLoading={false}
        error={null}
        onRetry={onRetryMock}
        onSnapshotCreated={onSnapshotCreatedMock}
      />
    );

    expect(screen.getByText('Versión 1')).toBeInTheDocument();
    expect(screen.getByText('Versión 2')).toBeInTheDocument();
    expect(screen.getByText('Versión Activa')).toBeInTheDocument();
    expect(screen.getByText('(Versión Raíz)')).toBeInTheDocument();
    expect(screen.getByText('alice')).toBeInTheDocument();
    expect(screen.getByText('bob')).toBeInTheDocument();
  });

  it('expands and collapses snapshot details', async () => {
    const user = userEvent.setup();

    render(
      <ContextTimeline
        project={mockProject}
        snapshots={mockSnapshots}
        isLoading={false}
        error={null}
        onRetry={onRetryMock}
        onSnapshotCreated={onSnapshotCreatedMock}
      />
    );

    // Initial state: details not visible
    expect(screen.queryByText('Hipótesis v2')).not.toBeInTheDocument();

    const detailButtons = screen.getAllByRole('button', { name: /Detalles/i });
    // Click details for Version 2 (second button)
    await user.click(detailButtons[1]);

    expect(screen.getByText('Hipótesis v2')).toBeInTheDocument();
    expect(screen.getByText('AUC >= 0.85')).toBeInTheDocument();

    // Click Ocultar
    const hideBtn = screen.getByRole('button', { name: /Ocultar/i });
    await user.click(hideBtn);

    expect(screen.queryByText('Hipótesis v2')).not.toBeInTheDocument();
  });

  it('copies hash to clipboard when clicking copy button', async () => {
    const user = userEvent.setup();
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: writeTextMock },
      configurable: true,
      writable: true,
    });

    render(
      <ContextTimeline
        project={mockProject}
        snapshots={mockSnapshots}
        isLoading={false}
        error={null}
        onRetry={onRetryMock}
        onSnapshotCreated={onSnapshotCreatedMock}
      />
    );

    const copyBtn = screen.getByLabelText('Copiar hash de la versión 1');
    await user.click(copyBtn);

    expect(writeTextMock).toHaveBeenCalledWith(mockSnapshots[0].content_hash);
  });
});
