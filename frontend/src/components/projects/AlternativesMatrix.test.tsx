import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AlternativesMatrix } from './AlternativesMatrix';
import { DecisionRead } from '../../types/projects';

const mockDecidedDecision: DecisionRead = {
  id: 'dec-1',
  project_id: 'proj-1',
  decision_type: 'select_alternative',
  question: '¿Qué algoritmo usar?',
  options: ['supervised_tabular_classification', 'heuristic_business_rule_engine'],
  selected_option: 'supervised_tabular_classification',
  rationale: 'Mayor precisión en datos históricos tabulares.',
  status: 'decided',
  evidence_artifact_ids: [],
  evidence_artifact_refs: [],
  decided_by: 'lead-data-scientist',
  decided_at: '2026-10-26T12:00:00Z',
  created_at: '2026-10-26T12:00:00Z',
};

describe('AlternativesMatrix Component', () => {
  it('renders standard M1 alternatives with technical attributes', () => {
    render(<AlternativesMatrix decisions={[]} />);

    expect(screen.getByText('Matriz Comparativa de Alternativas Analíticas (M1)')).toBeInTheDocument();
    expect(screen.getByText('Clasificación Supervisada Tabular')).toBeInTheDocument();
    expect(screen.getByText('Motor Heurístico de Reglas de Negocio')).toBeInTheDocument();
    expect(screen.getByText('Detección de Anomalías y Agrupamiento')).toBeInTheDocument();

    expect(screen.getByText('Evidencia Alta')).toBeInTheDocument();
    expect(screen.getByText('Evidencia Media')).toBeInTheDocument();
    expect(screen.getByText('Evidencia Preliminar')).toBeInTheDocument();
  });

  it('triggers onOpenDecisionModal when clicking Formalizar Selección', async () => {
    const user = userEvent.setup();
    const handleOpen = vi.fn();

    render(<AlternativesMatrix decisions={[]} onOpenDecisionModal={handleOpen} />);

    const button = screen.getByRole('button', { name: /Formalizar Selección/i });
    await user.click(button);

    expect(handleOpen).toHaveBeenCalledTimes(1);
  });

  it('renders adopted alternative banner when a select_alternative decision is decided', () => {
    render(<AlternativesMatrix decisions={[mockDecidedDecision]} />);

    const banner = screen.getByTestId('adopted-alternative-banner');
    expect(banner).toBeInTheDocument();
    expect(within(banner).getByText('supervised_tabular_classification')).toBeInTheDocument();
    expect(screen.getByText(/Mayor precisión en datos históricos/i)).toBeInTheDocument();
    expect(screen.getByText(/lead-data-scientist/i)).toBeInTheDocument();

    // Check card highlights
    const adoptedCard = screen.getByTestId('alternative-card-supervised_tabular_classification');
    expect(adoptedCard).toBeInTheDocument();
    expect(adoptedCard).toHaveTextContent('Adoptada');
  });
});
