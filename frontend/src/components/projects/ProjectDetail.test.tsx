import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ProjectDetail } from './ProjectDetail';
import * as projectsApi from '../../api/projects';
import * as contextApi from '../../api/context';
import * as decisionsApi from '../../api/decisions';
import * as auditApi from '../../api/audit';
import { ProjectRead, ContextRead, DecisionRead, AuditEventRead } from '../../types/projects';

describe('ProjectDetail Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.clearAllTimers();
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

  const mockSnapshot: ContextRead = {
    id: 'ctx-12345',
    project_id: 'proj-12345-uuid',
    version: 1,
    predecessor_id: null,
    content_hash: 'abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
    context: {
      company_name: 'Empresa Detalle S.A.',
      company_description: 'Servicios de logística avanzada.',
      business_need: 'Reducir retrasos en entregas de última milla.',
      expected_objective: 'Modelo predictivo de tiempos de entrega.',
      business_rules: ['No exceder 12 horas de jornada'],
      constraints: ['Procesamiento local sin nube'],
      assumptions: ['Se asume flota vehicular homogénea'],
      success_criteria: ['MAE inferior a 15 minutos'],
    },
    created_by: 'lead-analyst',
    created_at: '2026-10-26T12:00:00Z',
  };

  const mockDecision: DecisionRead = {
    id: 'dec-12345',
    project_id: 'proj-12345-uuid',
    decision_type: 'select_alternative',
    question: '¿Qué algoritmo usar para predicción de tiempos?',
    options: ['gradient_boosting', 'linear_regression'],
    selected_option: 'gradient_boosting',
    rationale: 'Captura mejor no-linealidades en tráfico vehicular.',
    status: 'decided',
    evidence_artifact_ids: [],
    evidence_artifact_refs: [],
    decided_by: 'lead-analyst',
    decided_at: '2026-10-26T12:30:00Z',
    created_at: '2026-10-26T12:00:00Z',
  };

  const mockAuditEvent: AuditEventRead = {
    id: 'evt-12345',
    project_id: 'proj-12345-uuid',
    actor_type: 'user',
    actor_id: 'lead-analyst',
    action: 'project.created',
    entity_type: 'project',
    entity_id: 'proj-12345-uuid',
    module_id: 'M1',
    correlation_id: 'corr-12345-uuid',
    metadata: { company_name: 'Empresa Detalle S.A.' },
    created_at: '2026-10-26T12:00:00Z',
    input_hash: '1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
    output_hash: 'abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
  };

  it('renders loading state initially and then shows project details', async () => {
    vi.spyOn(projectsApi, 'getProject').mockResolvedValueOnce(mockProject);
    vi.spyOn(contextApi, 'listContextSnapshots').mockResolvedValueOnce([]);
    vi.spyOn(decisionsApi, 'listDecisions').mockResolvedValueOnce([]);
    vi.spyOn(auditApi, 'listAuditEvents').mockResolvedValueOnce([]);

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
    vi.spyOn(contextApi, 'listContextSnapshots').mockResolvedValueOnce([]);
    vi.spyOn(decisionsApi, 'listDecisions').mockResolvedValueOnce([]);
    vi.spyOn(auditApi, 'listAuditEvents').mockResolvedValueOnce([]);

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
    vi.spyOn(contextApi, 'listContextSnapshots').mockResolvedValueOnce([]);
    vi.spyOn(decisionsApi, 'listDecisions').mockResolvedValueOnce([]);
    vi.spyOn(auditApi, 'listAuditEvents').mockResolvedValueOnce([]);

    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: writeTextMock },
      configurable: true,
      writable: true,
    });

    const { unmount } = render(<ProjectDetail projectId="proj-12345-uuid" onBack={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('Empresa Detalle S.A.')).toBeInTheDocument();
    });

    const copyButton = screen.getByRole('button', { name: /Copiar ID/i });
    await user.click(copyButton);

    expect(writeTextMock).toHaveBeenCalledWith('proj-12345-uuid');

    // Desmontar el componente debe limpiar el temporizador activo sin arrojar errores no controlados
    unmount();
  });

  it('displays error and allows retry when getProject fails', async () => {
    const user = userEvent.setup();
    const getProjectSpy = vi
      .spyOn(projectsApi, 'getProject')
      .mockRejectedValueOnce(new Error('Project not found'))
      .mockResolvedValueOnce(mockProject);
    vi.spyOn(contextApi, 'listContextSnapshots').mockResolvedValue([]);
    vi.spyOn(decisionsApi, 'listDecisions').mockResolvedValue([]);
    vi.spyOn(auditApi, 'listAuditEvents').mockResolvedValue([]);

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

  it('switches between tabs and displays context timeline, decisions, alternatives matrix and audit trail', async () => {
    const user = userEvent.setup();
    vi.spyOn(projectsApi, 'getProject').mockResolvedValue(mockProject);
    vi.spyOn(contextApi, 'listContextSnapshots').mockResolvedValue([mockSnapshot]);
    vi.spyOn(decisionsApi, 'listDecisions').mockResolvedValue([mockDecision]);
    vi.spyOn(auditApi, 'listAuditEvents').mockResolvedValue([mockAuditEvent]);

    render(<ProjectDetail projectId="proj-12345-uuid" onBack={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('Empresa Detalle S.A.')).toBeInTheDocument();
    });

    // Verify tabs buttons
    const contextTab = screen.getByRole('button', { name: /Instantáneas de Contexto/i });
    expect(contextTab).toBeInTheDocument();

    const decisionsTab = screen.getByRole('button', { name: /Decisiones de Negocio/i });
    expect(decisionsTab).toBeInTheDocument();

    const alternativesTab = screen.getByRole('button', { name: /Matriz de Alternativas/i });
    expect(alternativesTab).toBeInTheDocument();

    const auditTab = screen.getByRole('button', { name: /Pista de Auditoría/i });
    expect(auditTab).toBeInTheDocument();

    // 1. Click Context Snapshots tab
    await user.click(contextTab);
    expect(screen.getByText('Línea de Tiempo del Contexto de Negocio')).toBeInTheDocument();
    expect(screen.getByText('Versión 1')).toBeInTheDocument();
    expect(screen.getByText('Versión Activa')).toBeInTheDocument();

    // 2. Click Decisions tab
    await user.click(decisionsTab);
    expect(
      screen.getByText('¿Qué algoritmo usar para predicción de tiempos?')
    ).toBeInTheDocument();
    expect(screen.getByText('Decidida')).toBeInTheDocument();
    expect(screen.getByText('Adoptada')).toBeInTheDocument();

    // 3. Click Alternatives Matrix tab
    await user.click(alternativesTab);
    expect(screen.getByText(/Matriz Comparativa de Alternativas/i)).toBeInTheDocument();
    expect(screen.getByText('Clasificación Supervisada Tabular')).toBeInTheDocument();
    expect(screen.getByText('Motor Heurístico de Reglas de Negocio')).toBeInTheDocument();
    expect(screen.getByText('Detección de Anomalías y Agrupamiento')).toBeInTheDocument();

    // 4. Click Audit Trail tab
    await user.click(auditTab);
    expect(screen.getByText('Pista de Auditoría y Linaje del Proyecto')).toBeInTheDocument();
    expect(screen.getByText('project.created')).toBeInTheDocument();
    expect(screen.getByText('corr-12345-uuid')).toBeInTheDocument();

    // 5. Click back to Ficha General tab
    const generalTab = screen.getByRole('button', { name: /Ficha General/i });
    await user.click(generalTab);
    expect(screen.getByText('Criterios de Éxito Verificables')).toBeInTheDocument();
  });
});
