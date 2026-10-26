import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AuditTrailView } from './AuditTrailView';
import { AuditEventRead } from '../../types/projects';

const mockEvents: AuditEventRead[] = [
  {
    id: 'ev-1',
    project_id: 'proj-123',
    actor_type: 'user',
    actor_id: 'lead-architect',
    action: 'project.created',
    entity_type: 'project',
    entity_id: 'proj-123',
    module_id: null,
    input_hash: null,
    output_hash: null,
    correlation_id: 'corr-001',
    metadata: { company_name: 'Telco Global' },
    created_at: '2026-10-26T10:00:00Z',
  },
  {
    id: 'ev-2',
    project_id: 'proj-123',
    actor_type: 'user',
    actor_id: 'lead-architect',
    action: 'context.snapshot.created',
    entity_type: 'project_context_snapshot',
    entity_id: 'ctx-1',
    module_id: null,
    input_hash: 'sha256:1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff',
    output_hash: 'sha256:1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff',
    correlation_id: 'corr-002',
    metadata: { version: 1 },
    created_at: '2026-10-26T11:00:00Z',
  },
  {
    id: 'ev-3',
    project_id: 'proj-123',
    actor_type: 'user',
    actor_id: 'lead-architect',
    action: 'decision.created',
    entity_type: 'decision',
    entity_id: 'dec-1',
    module_id: null,
    input_hash: 'sha256:9999888877776666555544443333222211110000ffffddddccccbbbbaaaa9999',
    output_hash: null,
    correlation_id: 'corr-003',
    metadata: { decision_type: 'select_alternative', status: 'decided' },
    created_at: '2026-10-26T12:00:00Z',
  },
];

describe('AuditTrailView Component', () => {
  const onRetryMock = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state when isLoading is true', () => {
    render(
      <AuditTrailView
        projectId="proj-123"
        events={[]}
        isLoading={true}
        error={null}
        onRetry={onRetryMock}
      />
    );

    expect(screen.getByTestId('audit-loading')).toBeInTheDocument();
  });

  it('renders error state and handles retry click', async () => {
    const user = userEvent.setup();

    render(
      <AuditTrailView
        projectId="proj-123"
        events={[]}
        isLoading={false}
        error="Error 500 al consultar auditoría"
        onRetry={onRetryMock}
      />
    );

    expect(screen.getByTestId('audit-error')).toBeInTheDocument();
    expect(screen.getByText('Error 500 al consultar auditoría')).toBeInTheDocument();

    const retryBtn = screen.getByRole('button', { name: /Reintentar consulta/i });
    await user.click(retryBtn);

    expect(onRetryMock).toHaveBeenCalledTimes(1);
  });

  it('renders empty state when there are no events', () => {
    render(
      <AuditTrailView
        projectId="proj-123"
        events={[]}
        isLoading={false}
        error={null}
        onRetry={onRetryMock}
      />
    );

    expect(screen.getByTestId('audit-empty')).toBeInTheDocument();
    expect(screen.getByText('Sin eventos de auditoría registrados')).toBeInTheDocument();
  });

  it('renders events with action badges, correlation and metadata in chronological order', () => {
    render(
      <AuditTrailView
        projectId="proj-123"
        events={mockEvents}
        isLoading={false}
        error={null}
        onRetry={onRetryMock}
      />
    );

    expect(screen.getByText('project.created')).toBeInTheDocument();
    expect(screen.getByText('context.snapshot.created')).toBeInTheDocument();
    expect(screen.getByText('decision.created')).toBeInTheDocument();

    expect(screen.getByText('corr-001')).toBeInTheDocument();
    expect(screen.getByText('corr-002')).toBeInTheDocument();
    expect(screen.getByText('corr-003')).toBeInTheDocument();

    expect(screen.getByTestId('audit-events-count-badge')).toHaveTextContent('3 eventos');
  });

  it('toggles sort order between chronological and newest first', async () => {
    const user = userEvent.setup();

    render(
      <AuditTrailView
        projectId="proj-123"
        events={mockEvents}
        isLoading={false}
        error={null}
        onRetry={onRetryMock}
      />
    );

    const toggleBtn = screen.getByRole('button', { name: /Orden:/i });
    expect(toggleBtn).toHaveTextContent('Orden: Más antiguos primero');

    await user.click(toggleBtn);
    expect(toggleBtn).toHaveTextContent('Orden: Más recientes primero');
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
      <AuditTrailView
        projectId="proj-123"
        events={mockEvents}
        isLoading={false}
        error={null}
        onRetry={onRetryMock}
      />
    );

    const copyBtn = screen.getByLabelText('Copiar input hash del evento ev-2');
    await user.click(copyBtn);

    expect(writeTextMock).toHaveBeenCalledWith(mockEvents[1].input_hash);
  });
});
