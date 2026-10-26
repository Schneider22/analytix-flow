import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ProjectDetail } from './ProjectDetail';
import * as projectsApi from '../../api/projects';
import { ProjectRead } from '../../types/projects';

describe('ProjectDetail Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const mockProject: ProjectRead = {
    id: 'proj-12345-uuid',
    company_name: 'Empresa Detalle S.A.',
    company_description: 'Servicios de logística avanzada.',
    business_need: 'Reducir retrasos en entregas de última milla.',
    expected_objective: 'Modelo predictivo de tiempos de entrega.',
    business_rules: ['No exceder 12 horas de jornada'],
    constraints: ['Procesamiento local sin nube'],
    success_criteria: ['MAE inferior a 15 minutos'],
    owner_id: 'lead-analyst',
    organization_id: null,
    status: 'draft',
    current_phase: 'business_understanding',
    created_at: '2026-10-26T12:00:00Z',
    updated_at: '2026-10-26T12:00:00Z',
  };

  it('renders loading state initially and then shows project details', async () => {
    vi.spyOn(projectsApi, 'getProject').mockResolvedValueOnce(mockProject);

    render(<ProjectDetail projectId="proj-12345-uuid" onBack={vi.fn()} />);

    expect(screen.getByTestId('project-detail-loading')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Empresa Detalle S.A.')).toBeInTheDocument();
    });

    expect(screen.getByText('Servicios de logística avanzada.')).toBeInTheDocument();
    expect(screen.getByText('Reducir retrasos en entregas de última milla.')).toBeInTheDocument();
    expect(screen.getByText('Modelo predictivo de tiempos de entrega.')).toBeInTheDocument();
    expect(screen.getByText('MAE inferior a 15 minutos')).toBeInTheDocument();
    expect(screen.getByText('No exceder 12 horas de jornada')).toBeInTheDocument();
    expect(screen.getByText('Procesamiento local sin nube')).toBeInTheDocument();
    expect(screen.getByText('proj-12345-uuid')).toBeInTheDocument();
    expect(screen.getByText('draft')).toBeInTheDocument();
  });

  it('calls onBack when clicking the back button', async () => {
    const user = userEvent.setup();
    const handleBack = vi.fn();
    vi.spyOn(projectsApi, 'getProject').mockResolvedValueOnce(mockProject);

    render(<ProjectDetail projectId="proj-12345-uuid" onBack={handleBack} />);

    await waitFor(() => {
      expect(screen.getByText('Empresa Detalle S.A.')).toBeInTheDocument();
    });

    const backButton = screen.getByRole('button', { name: /Volver a la lista/i });
    await user.click(backButton);

    expect(handleBack).toHaveBeenCalled();
  });

  it('copies project ID when clicking copy button', async () => {
    const user = userEvent.setup();
    vi.spyOn(projectsApi, 'getProject').mockResolvedValueOnce(mockProject);

    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: writeTextMock },
      configurable: true,
      writable: true,
    });

    render(<ProjectDetail projectId="proj-12345-uuid" onBack={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('Empresa Detalle S.A.')).toBeInTheDocument();
    });

    const copyButton = screen.getByRole('button', { name: /Copiar ID/i });
    await user.click(copyButton);

    expect(writeTextMock).toHaveBeenCalledWith('proj-12345-uuid');
  });

  it('displays error and allows retry when getProject fails', async () => {
    const user = userEvent.setup();
    const getProjectSpy = vi
      .spyOn(projectsApi, 'getProject')
      .mockRejectedValueOnce(new Error('Project not found'))
      .mockResolvedValueOnce(mockProject);

    render(<ProjectDetail projectId="proj-12345-uuid" onBack={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTestId('project-detail-error')).toBeInTheDocument();
    });

    expect(screen.getByText('Project not found')).toBeInTheDocument();

    const retryButton = screen.getByRole('button', { name: /Reintentar/i });
    await user.click(retryButton);

    await waitFor(() => {
      expect(screen.getByText('Empresa Detalle S.A.')).toBeInTheDocument();
    });

    expect(getProjectSpy).toHaveBeenCalledTimes(2);
  });
});
