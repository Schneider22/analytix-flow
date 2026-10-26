import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DecisionCreateModal } from './DecisionCreateModal';
import * as decisionsApi from '../../api/decisions';
import { DecisionRead } from '../../types/projects';

vi.mock('../../api/decisions');

describe('DecisionCreateModal Component', () => {
  const onCloseMock = vi.fn();
  const onDecisionCreatedMock = vi.fn();
  const projectId = 'proj-12345678-abcd-ef01-2345-6789abcdef01';

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders modal with initial state', () => {
    render(
      <DecisionCreateModal
        isOpen={true}
        onClose={onCloseMock}
        projectId={projectId}
        defaultDecidedBy="lead-architect"
        onDecisionCreated={onDecisionCreatedMock}
      />
    );

    expect(screen.getByText('Registrar Decisión de Negocio')).toBeInTheDocument();
    expect(screen.getByText(/¿Evaluar alternativas analíticas para M1\?/i)).toBeInTheDocument();
  });

  it('loads M1 alternative template when clicking Cargar Plantilla M1', async () => {
    const user = userEvent.setup();

    render(
      <DecisionCreateModal
        isOpen={true}
        onClose={onCloseMock}
        projectId={projectId}
        defaultDecidedBy="lead-architect"
        onDecisionCreated={onDecisionCreatedMock}
      />
    );

    const templateBtn = screen.getByRole('button', { name: /Cargar Plantilla M1/i });
    await user.click(templateBtn);

    const questionInput = screen.getByLabelText(/Pregunta de Decisión/i) as HTMLTextAreaElement;
    expect(questionInput.value).toContain('¿Qué estrategia de modelado analítico');

    expect(screen.getAllByText('supervised_tabular_classification').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('heuristic_business_rule_engine').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('unsupervised_anomaly_clustering').length).toBeGreaterThanOrEqual(1);

    const statusSelect = screen.getByLabelText(/Estado de la Decisión/i) as HTMLSelectElement;
    expect(statusSelect.value).toBe('decided');

    const selectedOptionSelect = screen.getByLabelText(/Opción Seleccionada/i) as HTMLSelectElement;
    expect(selectedOptionSelect.value).toBe('supervised_tabular_classification');
  });

  it('validates required fields before submitting', async () => {
    const user = userEvent.setup();

    render(
      <DecisionCreateModal
        isOpen={true}
        onClose={onCloseMock}
        projectId={projectId}
        defaultDecidedBy="lead-architect"
        onDecisionCreated={onDecisionCreatedMock}
      />
    );

    const submitBtn = screen.getByRole('button', { name: /Registrar Decisión/i });
    await user.click(submitBtn);

    expect(screen.getByText('La pregunta de decisión es obligatoria')).toBeInTheDocument();
    expect(screen.getByText('Debes añadir al menos una opción a evaluar')).toBeInTheDocument();
    expect(decisionsApi.createDecision).not.toHaveBeenCalled();
  });

  it('validates selected_option and decided_by when status is decided', async () => {
    const user = userEvent.setup();

    render(
      <DecisionCreateModal
        isOpen={true}
        onClose={onCloseMock}
        projectId={projectId}
        defaultDecidedBy=""
        onDecisionCreated={onDecisionCreatedMock}
      />
    );

    const questionInput = screen.getByLabelText(/Pregunta de Decisión/i);
    await user.type(questionInput, '¿Cuál algoritmo usar?');

    const optionInput = screen.getByPlaceholderText(/supervised_tabular_classification/i);
    await user.type(optionInput, 'random_forest');
    await user.click(screen.getByRole('button', { name: /Añadir/i }));

    const statusSelect = screen.getByLabelText(/Estado de la Decisión/i);
    await user.selectOptions(statusSelect, 'decided');

    const submitBtn = screen.getByRole('button', { name: /Registrar Decisión/i });
    await user.click(submitBtn);

    expect(
      screen.getByText('Cuando el estado es "decided", debes seleccionar una opción válida de la lista')
    ).toBeInTheDocument();
    expect(
      screen.getByText('Cuando el estado es "decided", el campo "decided_by" (responsable) es obligatorio')
    ).toBeInTheDocument();
  });

  it('successfully creates a decision and calls callbacks', async () => {
    const user = userEvent.setup();
    const createdMock: DecisionRead = {
      id: 'dec-11111111-2222-3333-4444-555555555555',
      project_id: projectId,
      decision_type: 'select_alternative',
      question: '¿Qué algoritmo usar?',
      options: ['lightgbm', 'xgboost'],
      selected_option: 'lightgbm',
      rationale: 'Mayor velocidad en CPU',
      status: 'decided',
      evidence_artifact_ids: [],
      evidence_artifact_refs: [],
      decided_by: 'lead-architect',
      decided_at: '2026-03-30T10:00:00Z',
      created_at: '2026-03-30T10:00:00Z',
    };
    vi.mocked(decisionsApi.createDecision).mockResolvedValue(createdMock);

    render(
      <DecisionCreateModal
        isOpen={true}
        onClose={onCloseMock}
        projectId={projectId}
        defaultDecidedBy="lead-architect"
        onDecisionCreated={onDecisionCreatedMock}
      />
    );

    // Click template to prefill quickly
    const templateBtn = screen.getByRole('button', { name: /Cargar Plantilla M1/i });
    await user.click(templateBtn);

    const submitBtn = screen.getByRole('button', { name: /Registrar Decisión/i });
    await user.click(submitBtn);

    await waitFor(() => {
      expect(decisionsApi.createDecision).toHaveBeenCalledTimes(1);
    });

    expect(decisionsApi.createDecision).toHaveBeenCalledWith(
      projectId,
      expect.objectContaining({
        decision_type: 'select_alternative',
        status: 'decided',
        selected_option: 'supervised_tabular_classification',
        evidence_artifact_ids: [],
        evidence_artifact_refs: [],
        decided_by: 'lead-architect',
      })
    );

    expect(onDecisionCreatedMock).toHaveBeenCalledWith(createdMock);
    expect(onCloseMock).toHaveBeenCalled();
  });
});
