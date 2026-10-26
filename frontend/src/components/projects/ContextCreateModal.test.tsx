import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ContextCreateModal } from './ContextCreateModal';
import * as contextApi from '../../api/context';
import { ContextRead, ProjectRead } from '../../types/projects';

vi.mock('../../api/context');

const mockProject: ProjectRead = {
  id: 'proj-12345678-abcd-ef01-2345-6789abcdef01',
  company_name: 'Telco Global Corp',
  company_description: 'Proveedor de servicios móviles y fibra óptica',
  business_need: 'Reducir tasa de churn del 15% al 10%',
  expected_objective: 'Modelo predictivo con AUC >= 0.80',
  business_rules: ['Tratar cuentas sin consumo como churn'],
  constraints: ['Tiempo de respuesta < 200ms'],
  success_criteria: ['Recall >= 0.75 en segmento premium'],
  owner_id: 'lead-architect',
  organization_id: 'org-123',
  status: 'draft',
  current_phase: 'business_understanding',
  created_at: '2026-03-30T10:00:00Z',
  updated_at: '2026-03-30T10:00:00Z',
};

const mockSnapshot: ContextRead = {
  id: 'ctx-11111111-2222-3333-4444-555555555555',
  project_id: 'proj-12345678-abcd-ef01-2345-6789abcdef01',
  version: 1,
  predecessor_id: null,
  content_hash: 'a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef',
  context: {
    company_name: 'Telco Global Corp',
    company_description: 'Proveedor de servicios móviles y fibra óptica actualizado',
    business_need: 'Reducir tasa de churn del 15% al 8%',
    expected_objective: 'Modelo predictivo con AUC >= 0.85',
    business_rules: ['Regla v1'],
    constraints: ['Restricción v1'],
    assumptions: ['Hipótesis v1: datos estables en Q1'],
    success_criteria: ['Recall >= 0.80'],
  },
  created_by: 'lead-data-scientist',
  created_at: '2026-03-30T12:00:00Z',
};

describe('ContextCreateModal Component', () => {
  const onCloseMock = vi.fn();
  const onSnapshotCreatedMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders correctly preloaded from base project when there is no previous snapshot', () => {
    render(
      <ContextCreateModal
        isOpen={true}
        onClose={onCloseMock}
        project={mockProject}
        latestSnapshot={null}
        onSnapshotCreated={onSnapshotCreatedMock}
      />
    );

    expect(screen.getByText('Registrar Nueva Instantánea de Contexto')).toBeInTheDocument();
    expect(screen.getByText('v1')).toBeInTheDocument();

    const companyInput = screen.getByLabelText(/Nombre de la Empresa/i) as HTMLInputElement;
    expect(companyInput.value).toBe('Telco Global Corp');

    const authorInput = screen.getByLabelText(/Autor \/ Responsable/i) as HTMLInputElement;
    expect(authorInput.value).toBe('lead-architect');
  });

  it('renders correctly preloaded from latest snapshot and shows next version', () => {
    render(
      <ContextCreateModal
        isOpen={true}
        onClose={onCloseMock}
        project={mockProject}
        latestSnapshot={mockSnapshot}
        onSnapshotCreated={onSnapshotCreatedMock}
      />
    );

    expect(screen.getByText('v2')).toBeInTheDocument();
    expect(screen.getByText(/Predecesor: v1/i)).toBeInTheDocument();

    const authorInput = screen.getByLabelText(/Autor \/ Responsable/i) as HTMLInputElement;
    expect(authorInput.value).toBe('lead-data-scientist');
  });

  it('validates required fields before submitting', async () => {
    const user = userEvent.setup();

    render(
      <ContextCreateModal
        isOpen={true}
        onClose={onCloseMock}
        project={mockProject}
        latestSnapshot={null}
        onSnapshotCreated={onSnapshotCreatedMock}
      />
    );

    const authorInput = screen.getByLabelText(/Autor \/ Responsable/i);
    await user.clear(authorInput);

    const submitBtn = screen.getByRole('button', { name: /Registrar Instantánea v1/i });
    await user.click(submitBtn);

    expect(screen.getByText('El campo created_by (autor) es obligatorio')).toBeInTheDocument();
    expect(contextApi.createContextSnapshot).not.toHaveBeenCalled();
  });

  it('submits successfully and calls onSnapshotCreated and onClose', async () => {
    const user = userEvent.setup();
    const createdResult: ContextRead = {
      ...mockSnapshot,
      version: 2,
      predecessor_id: mockSnapshot.id,
    };
    vi.mocked(contextApi.createContextSnapshot).mockResolvedValue(createdResult);

    render(
      <ContextCreateModal
        isOpen={true}
        onClose={onCloseMock}
        project={mockProject}
        latestSnapshot={mockSnapshot}
        onSnapshotCreated={onSnapshotCreatedMock}
      />
    );

    const submitBtn = screen.getByRole('button', { name: /Registrar Instantánea v2/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(contextApi.createContextSnapshot).toHaveBeenCalledTimes(1);
    });

    expect(contextApi.createContextSnapshot).toHaveBeenCalledWith(
      mockProject.id,
      expect.objectContaining({
        created_by: 'lead-data-scientist',
        context: expect.objectContaining({
          company_name: 'Telco Global Corp',
          assumptions: ['Hipótesis v1: datos estables en Q1'],
        }),
      })
    );

    expect(onSnapshotCreatedMock).toHaveBeenCalledWith(createdResult);
    expect(onCloseMock).toHaveBeenCalled();
  });
});
