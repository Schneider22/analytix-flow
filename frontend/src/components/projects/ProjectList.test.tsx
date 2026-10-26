import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ProjectList } from './ProjectList';
import { ProjectRead } from '../../types/projects';

describe('ProjectList Component', () => {
  const mockProjects: ProjectRead[] = [
    {
      id: 'proj-1',
      company_name: 'Empresa Alfa',
      company_description: 'Descripción Alfa',
      business_need: 'Necesidad Alfa',
      expected_objective: 'Objetivo Alfa',
      business_rules: [],
      constraints: [],
      success_criteria: ['Criterio Alfa 1', 'Criterio Alfa 2'],
      owner_id: 'owner-1',
      organization_id: null,
      status: 'draft',
      current_phase: 'business_understanding',
      created_at: '2026-10-26T10:00:00Z',
      updated_at: '2026-10-26T10:00:00Z',
    },
  ];

  it('renders project list with cards and project count badge', () => {
    render(
      <ProjectList
        projects={mockProjects}
        isLoading={false}
        errorMessage={null}
        onRefresh={vi.fn()}
        onSelectProject={vi.fn()}
        onOpenCreateModal={vi.fn()}
      />
    );

    expect(screen.getByText('Proyectos Registrados')).toBeInTheDocument();
    expect(screen.getByTestId('project-count-badge')).toHaveTextContent('1');
    expect(screen.getByText('Empresa Alfa')).toBeInTheDocument();
    expect(screen.getByText('Necesidad Alfa')).toBeInTheDocument();
    expect(screen.getByText(/2 definidos/)).toBeInTheDocument();
  });

  it('renders empty state when projects array is empty', () => {
    render(
      <ProjectList
        projects={[]}
        isLoading={false}
        errorMessage={null}
        onRefresh={vi.fn()}
        onSelectProject={vi.fn()}
        onOpenCreateModal={vi.fn()}
      />
    );

    expect(screen.getByTestId('project-list-empty')).toBeInTheDocument();
    expect(screen.getByText('No hay proyectos registrados aún')).toBeInTheDocument();
  });

  it('renders loading state when isLoading is true', () => {
    render(
      <ProjectList
        projects={[]}
        isLoading={true}
        errorMessage={null}
        onRefresh={vi.fn()}
        onSelectProject={vi.fn()}
        onOpenCreateModal={vi.fn()}
      />
    );

    expect(screen.getByTestId('project-list-loading')).toBeInTheDocument();
  });

  it('renders error state and triggers retry', async () => {
    const user = userEvent.setup();
    const handleRefresh = vi.fn();

    render(
      <ProjectList
        projects={[]}
        isLoading={false}
        errorMessage="Fallo de conexión"
        onRefresh={handleRefresh}
        onSelectProject={vi.fn()}
        onOpenCreateModal={vi.fn()}
      />
    );

    expect(screen.getByTestId('project-list-error')).toBeInTheDocument();
    expect(screen.getByText('Fallo de conexión')).toBeInTheDocument();

    const retryButton = screen.getByRole('button', { name: /Reintentar/i });
    await user.click(retryButton);

    expect(handleRefresh).toHaveBeenCalled();
  });

  it('calls onSelectProject when clicking Ver detalle', async () => {
    const user = userEvent.setup();
    const handleSelect = vi.fn();

    render(
      <ProjectList
        projects={mockProjects}
        isLoading={false}
        errorMessage={null}
        onRefresh={vi.fn()}
        onSelectProject={handleSelect}
        onOpenCreateModal={vi.fn()}
      />
    );

    const detailButton = screen.getByRole('button', { name: /Ver detalle/i });
    await user.click(detailButton);

    expect(handleSelect).toHaveBeenCalledWith('proj-1');
  });

  it('calls onOpenCreateModal when clicking Nuevo Proyecto', async () => {
    const user = userEvent.setup();
    const handleOpen = vi.fn();

    render(
      <ProjectList
        projects={[]}
        isLoading={false}
        errorMessage={null}
        onRefresh={vi.fn()}
        onSelectProject={vi.fn()}
        onOpenCreateModal={handleOpen}
      />
    );

    const newButton = screen.getByRole('button', { name: /Crear Primer Proyecto/i });
    await user.click(newButton);

    expect(handleOpen).toHaveBeenCalled();
  });
});
