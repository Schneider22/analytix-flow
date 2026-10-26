import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DecisionList } from './DecisionList';
import { DecisionRead } from '../../types/projects';

const mockDecisions: DecisionRead[] = [
  {
    id: 'dec-11111111-2222-3333-4444-555555555555',
    project_id: 'proj-123',
    decision_type: 'select_alternative',
    question: '¿Qué estrategia de modelado analítico debe implementarse para este problema?',
    options: [
      'supervised_tabular_classification',
      'heuristic_business_rule_engine',
      'unsupervised_anomaly_clustering',
    ],
    selected_option: 'supervised_tabular_classification',
    rationale: 'Evaluación técnica basada en datos etiquetados y métricas de negocio.',
    status: 'decided',
    evidence_artifact_ids: [],
    evidence_artifact_refs: [],
    decided_by: 'lead-data-scientist',
    decided_at: '2026-03-30T14:30:00Z',
    created_at: '2026-03-30T14:00:00Z',
  },
  {
    id: 'dec-22222222-3333-4444-5555-666666666666',
    project_id: 'proj-123',
    decision_type: 'feature_selection',
    question: '¿Incluir variables de geolocalización?',
    options: ['incluir_todas', 'solo_pais_ciudad', 'excluir_por_privacidad'],
    selected_option: null,
    rationale: 'En espera de revisión legal sobre privacidad de datos.',
    status: 'pending',
    evidence_artifact_ids: [],
    evidence_artifact_refs: [],
    decided_by: null,
    decided_at: null,
    created_at: '2026-03-30T15:00:00Z',
  },
];

describe('DecisionList Component', () => {
  const onRetryMock = vi.fn();
  const onDecisionCreatedMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state when isLoading is true', () => {
    render(
      <DecisionList
        projectId="proj-123"
        decisions={[]}
        isLoading={true}
        error={null}
        onRetry={onRetryMock}
        onDecisionCreated={onDecisionCreatedMock}
      />
    );

    expect(screen.getByText(/Cargando decisiones de negocio/i)).toBeInTheDocument();
  });

  it('renders error state and allows retry', async () => {
    const user = userEvent.setup();

    render(
      <DecisionList
        projectId="proj-123"
        decisions={[]}
        isLoading={false}
        error="Error 500 al conectar con el servidor"
        onRetry={onRetryMock}
        onDecisionCreated={onDecisionCreatedMock}
      />
    );

    expect(screen.getByText('Error al cargar las decisiones de negocio')).toBeInTheDocument();
    expect(screen.getByText('Error 500 al conectar con el servidor')).toBeInTheDocument();

    const retryBtn = screen.getByRole('button', { name: /Reintentar carga/i });
    await user.click(retryBtn);

    expect(onRetryMock).toHaveBeenCalledTimes(1);
  });

  it('renders empty state when there are no decisions', () => {
    render(
      <DecisionList
        projectId="proj-123"
        decisions={[]}
        isLoading={false}
        error={null}
        onRetry={onRetryMock}
        onDecisionCreated={onDecisionCreatedMock}
      />
    );

    expect(screen.getByText('Sin decisiones de negocio registradas')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Registrar Primera Decisión/i })).toBeInTheDocument();
  });

  it('renders decision items with status badges and highlighted adopted option', () => {
    render(
      <DecisionList
        projectId="proj-123"
        decisions={mockDecisions}
        isLoading={false}
        error={null}
        onRetry={onRetryMock}
        onDecisionCreated={onDecisionCreatedMock}
      />
    );

    expect(
      screen.getByText('¿Qué estrategia de modelado analítico debe implementarse para este problema?')
    ).toBeInTheDocument();
    expect(screen.getByText('Decidida')).toBeInTheDocument();
    expect(screen.getByText('Pendiente')).toBeInTheDocument();
    expect(screen.getByText('Adoptada')).toBeInTheDocument();
    expect(screen.getByText('lead-data-scientist')).toBeInTheDocument();
    expect(
      screen.getByText('Evaluación técnica basada en datos etiquetados y métricas de negocio.')
    ).toBeInTheDocument();
  });

  it('opens DecisionCreateModal when clicking Registrar Decisión', async () => {
    const user = userEvent.setup();

    render(
      <DecisionList
        projectId="proj-123"
        decisions={mockDecisions}
        isLoading={false}
        error={null}
        onRetry={onRetryMock}
        onDecisionCreated={onDecisionCreatedMock}
      />
    );

    const openBtn = screen.getByRole('button', { name: /Registrar Decisión/i });
    await user.click(openBtn);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Registrar Decisión de Negocio')).toBeInTheDocument();
  });
});
