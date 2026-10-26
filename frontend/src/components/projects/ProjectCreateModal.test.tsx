import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ProjectCreateModal } from './ProjectCreateModal';
import * as projectsApi from '../../api/projects';
import { ProjectRead } from '../../types/projects';
import { ApiError } from '../../api/client';

describe('ProjectCreateModal Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  const mockCreated: ProjectRead = {
    id: 'new-proj-123',
    company_name: 'Test Corp',
    company_description: 'Test Description',
    business_need: 'Test Need',
    expected_objective: 'Test Objective',
    business_rules: [],
    constraints: [],
    success_criteria: ['Holdout F1 >= 0.70'],
    owner_id: 'test-user',
    organization_id: null,
    status: 'draft',
    current_phase: 'business_understanding',
    created_at: '2026-10-26T12:00:00Z',
    updated_at: '2026-10-26T12:00:00Z',
  };

  it('does not render when isOpen is false', () => {
    render(
      <ProjectCreateModal
        isOpen={false}
        onClose={vi.fn()}
        onProjectCreated={vi.fn()}
      />
    );

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('validates required fields before submitting', async () => {
    const user = userEvent.setup();
    render(
      <ProjectCreateModal
        isOpen={true}
        onClose={vi.fn()}
        onProjectCreated={vi.fn()}
      />
    );

    const submitButton = screen.getByRole('button', { name: /Crear Proyecto/i });
    await user.click(submitButton);

    expect(screen.getByText(/El nombre de la empresa es obligatorio/i)).toBeInTheDocument();
    expect(screen.getByText(/La descripción de la empresa es obligatoria/i)).toBeInTheDocument();
    expect(screen.getByText(/La necesidad de negocio es obligatoria/i)).toBeInTheDocument();
    expect(screen.getByText(/El objetivo esperado es obligatorio/i)).toBeInTheDocument();
    expect(screen.getByText(/Debes definir al menos un criterio de éxito verificable/i)).toBeInTheDocument();
  });

  it('submits successfully when all required fields and criteria are provided', async () => {
    const user = userEvent.setup();
    const handleClose = vi.fn();
    const handleCreated = vi.fn();

    vi.spyOn(projectsApi, 'createProject').mockResolvedValueOnce(mockCreated);

    render(
      <ProjectCreateModal
        isOpen={true}
        onClose={handleClose}
        onProjectCreated={handleCreated}
      />
    );

    await user.type(screen.getByLabelText(/Nombre de la Empresa/i), 'Test Corp');
    await user.type(screen.getByLabelText(/Descripción de la Empresa/i), 'Test Description');
    await user.type(screen.getByLabelText(/Necesidad o Problema de Negocio/i), 'Test Need');
    await user.type(screen.getByLabelText(/Objetivo Esperado/i), 'Test Objective');

    // Add success criterion
    const criterionInput = screen.getByPlaceholderText(/Ej. Holdout F1-score/i);
    await user.type(criterionInput, 'Holdout F1 >= 0.70');
    await user.click(screen.getByRole('button', { name: /Añadir a Criterios de Éxito/i }));

    const submitButton = screen.getByRole('button', { name: /Crear Proyecto/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(handleCreated).toHaveBeenCalledWith(mockCreated);
      expect(handleClose).toHaveBeenCalled();
    });
  });

  it('displays API error message when createProject rejects', async () => {
    const user = userEvent.setup();
    vi.spyOn(projectsApi, 'createProject').mockRejectedValueOnce(
      new ApiError(422, 'Nombre de empresa duplicado')
    );

    render(
      <ProjectCreateModal
        isOpen={true}
        onClose={vi.fn()}
        onProjectCreated={vi.fn()}
      />
    );

    await user.type(screen.getByLabelText(/Nombre de la Empresa/i), 'Test Corp');
    await user.type(screen.getByLabelText(/Descripción de la Empresa/i), 'Test Description');
    await user.type(screen.getByLabelText(/Necesidad o Problema de Negocio/i), 'Test Need');
    await user.type(screen.getByLabelText(/Objetivo Esperado/i), 'Test Objective');

    const criterionInput = screen.getByPlaceholderText(/Ej. Holdout F1-score/i);
    await user.type(criterionInput, 'Holdout F1 >= 0.70');
    await user.click(screen.getByRole('button', { name: /Añadir a Criterios de Éxito/i }));

    const submitButton = screen.getByRole('button', { name: /Crear Proyecto/i });
    await user.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/Nombre de empresa duplicado/i)).toBeInTheDocument();
    });
  });
});
