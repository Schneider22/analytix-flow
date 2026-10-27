import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App';
import * as healthApi from './api/health';
import * as projectsApi from './api/projects';
import { ApiError, NetworkError } from './api/client';
import { ProjectRead } from './types/projects';

describe('App Component', () => {
  const mockProject: ProjectRead = {
    id: 'proj-uuid-1',
    company_name: 'Telco Global',
    company_description: 'Telco provider',
    business_need: 'Churn reduction',
    expected_objective: 'Predict churn risk',
    business_rules: [],
    constraints: [],
    success_criteria: ['F1 >= 0.65'],
    owner_id: 'data-lead',
    organization_id: null,
    status: 'draft',
    current_phase: 'business_understanding',
    created_at: '2026-10-26T12:00:00Z',
    updated_at: '2026-10-26T12:00:00Z',
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(projectsApi, 'listProjects').mockResolvedValue([]);
    vi.spyOn(healthApi, 'getHealth').mockResolvedValue({
      status: 'ok',
      database: 'ok',
    });
  });

  it('renders initial screen with navbar and projects view by default', async () => {
    render(<App />);

    expect(screen.getByText('AnalytixFlow')).toBeInTheDocument();
    expect(screen.getByText('Business Portal')).toBeInTheDocument();
    expect(screen.getByText('Proyectos y Negocio (M1)')).toBeInTheDocument();
    expect(screen.getByText('Diagnóstico de Servicios')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Proyectos Registrados')).toBeInTheDocument();
      expect(screen.getByTestId('project-list-empty')).toBeInTheDocument();
    });
  });

  it('keeps status and archive filters synchronized in the API request', async () => {
    const user = userEvent.setup();
    vi.mocked(projectsApi.listProjects).mockResolvedValue([mockProject]);

    render(<App />);

    await waitFor(() => expect(screen.getByText('Telco Global')).toBeInTheDocument());

    const statusFilter = screen.getByLabelText(/Filtrar por estado/i);
    const archiveFilter = screen.getByLabelText(/Filtrar por archivado/i);

    await user.selectOptions(statusFilter, 'archived');
    await waitFor(() => {
      expect(projectsApi.listProjects).toHaveBeenLastCalledWith({ archived: 'only' });
      expect(archiveFilter).toHaveValue('only');
    });

    await user.selectOptions(statusFilter, 'active');
    await waitFor(() => {
      expect(projectsApi.listProjects).toHaveBeenLastCalledWith({ archived: 'exclude' });
      expect(archiveFilter).toHaveValue('exclude');
    });

    await user.selectOptions(archiveFilter, 'only');
    await waitFor(() => expect(statusFilter).toHaveValue('archived'));

    await user.selectOptions(archiveFilter, 'include');
    await waitFor(() => {
      expect(projectsApi.listProjects).toHaveBeenLastCalledWith({ archived: 'include' });
      expect(statusFilter).toHaveValue('all');
    });
  });

  it('switches to diagnostics view and displays services status card', async () => {
    const user = userEvent.setup();
    render(<App />);

    const diagButton = screen.getByRole('button', { name: /Diagnóstico de Servicios/i });
    await user.click(diagButton);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Diagnóstico de Servicios' })).toBeInTheDocument();
      expect(screen.getByTestId('status-badge')).toHaveTextContent('Disponible');
    });

    expect(screen.getByText('Gobernanza Humana')).toBeInTheDocument();
    expect(screen.getByText('Linaje Criptográfico')).toBeInTheDocument();
    expect(screen.getByText('Cero Fabricación')).toBeInTheDocument();
  });

  it('displays "No disponible" in diagnostics view when health check fails', async () => {
    const user = userEvent.setup();
    vi.spyOn(healthApi, 'getHealth').mockRejectedValueOnce(
      new NetworkError(new Error('Connection refused'))
    );

    render(<App />);

    const diagButton = screen.getByRole('button', { name: /Diagnóstico de Servicios/i });
    await user.click(diagButton);

    await waitFor(() => {
      expect(screen.getByTestId('status-badge')).toHaveTextContent('No disponible');
    });

    expect(screen.getByText(/Connection refused/)).toBeInTheDocument();
  });

  it('displays "No disponible" when backend returns HTTP 503 error', async () => {
    const user = userEvent.setup();
    vi.spyOn(healthApi, 'getHealth').mockRejectedValueOnce(
      new ApiError(503, 'Persistence service unavailable')
    );

    render(<App />);

    const diagButton = screen.getByRole('button', { name: /Diagnóstico de Servicios/i });
    await user.click(diagButton);

    await waitFor(() => {
      expect(screen.getByTestId('status-badge')).toHaveTextContent('No disponible');
    });

    expect(screen.getByText(/Persistence service unavailable/)).toBeInTheDocument();
  });

  it('navigates to project detail when selecting a project from list', async () => {
    const user = userEvent.setup();
    vi.spyOn(projectsApi, 'listProjects').mockResolvedValueOnce([mockProject]);
    vi.spyOn(projectsApi, 'getProject').mockResolvedValueOnce(mockProject);

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Telco Global')).toBeInTheDocument();
    });

    const detailButton = screen.getByRole('button', { name: /Ver detalle/i });
    await user.click(detailButton);

    await waitFor(() => {
      expect(screen.getByText('Ficha del Proyecto')).toBeInTheDocument();
      expect(screen.getByText('Predict churn risk')).toBeInTheDocument();
    });

    // Back to list
    const backButton = screen.getByRole('button', { name: /Volver a la lista/i });
    await user.click(backButton);

    await waitFor(() => {
      expect(screen.getByText('Proyectos Registrados')).toBeInTheDocument();
    });
  });

  it('opens create modal, creates project, and navigates to detail view', async () => {
    const user = userEvent.setup();
    vi.spyOn(projectsApi, 'createProject').mockResolvedValueOnce(mockProject);
    vi.spyOn(projectsApi, 'getProject').mockResolvedValueOnce(mockProject);

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('project-list-empty')).toBeInTheDocument();
    });

    const newProjectBtn = screen.getByRole('button', { name: /Nuevo Proyecto/i });
    await user.click(newProjectBtn);

    expect(screen.getByRole('dialog')).toBeInTheDocument();

    // Fill form
    await user.type(screen.getByLabelText(/Nombre de la Empresa/i), 'Telco Global');
    await user.type(screen.getByLabelText(/Descripción de la Empresa/i), 'Telco provider');
    await user.type(screen.getByLabelText(/Necesidad o Problema de Negocio/i), 'Churn reduction');
    await user.type(screen.getByLabelText(/Objetivo Esperado/i), 'Predict churn risk');

    const criterionInput = screen.getByPlaceholderText(/Ej. Holdout F1-score/i);
    await user.type(criterionInput, 'F1 >= 0.65');
    await user.click(screen.getByRole('button', { name: /Añadir a Criterios de Éxito/i }));

    const submitBtn = screen.getByRole('button', { name: /Crear Proyecto/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText('Ficha del Proyecto')).toBeInTheDocument();
      expect(screen.getByText('Telco Global')).toBeInTheDocument();
    });
  });
});
