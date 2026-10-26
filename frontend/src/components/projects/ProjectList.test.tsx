import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ProjectList } from './ProjectList';
import { ProjectRead } from '../../types/projects';

describe('ProjectList Component', () => {
  const mockProjects: ProjectRead[] = [
    {
      id: 'proj-1',
      company_name: 'Empresa Alfa Telecom',
      company_description: 'Descripción Alfa',
      business_need: 'Reducir tasa de abandono de clientes',
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
    {
      id: 'proj-2',
      company_name: 'Banco Beta Financiero',
      company_description: 'Servicios bancarios',
      business_need: 'Detectar fraude en transferencias inmediatas',
      expected_objective: 'Objetivo Beta',
      business_rules: [],
      constraints: [],
      success_criteria: ['Recall >= 0.85'],
      owner_id: 'owner-2',
      organization_id: null,
      status: 'active',
      current_phase: 'data_understanding',
      created_at: '2026-10-26T11:00:00Z',
      updated_at: '2026-10-26T11:00:00Z',
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
    expect(screen.getByTestId('project-count-badge')).toHaveTextContent('2');
    expect(screen.getByText('Empresa Alfa Telecom')).toBeInTheDocument();
    expect(screen.getByText('Banco Beta Financiero')).toBeInTheDocument();
  });

  it('filters projects reactively by search query', async () => {
    const user = userEvent.setup();

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

    const searchInput = screen.getByLabelText(/Buscar proyectos/i);
    await user.type(searchInput, 'fraude');

    expect(screen.getByText('Banco Beta Financiero')).toBeInTheDocument();
    expect(screen.queryByText('Empresa Alfa Telecom')).not.toBeInTheDocument();
    expect(screen.getByTestId('project-count-badge')).toHaveTextContent('Mostrando 1 de 2');
  });

  it('filters projects by status and shows empty state when no matches found', async () => {
    const user = userEvent.setup();

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

    const statusSelect = screen.getByLabelText(/Filtrar por estado/i);
    await user.selectOptions(statusSelect, 'archived');

    expect(screen.getByTestId('project-list-filtered-empty')).toBeInTheDocument();
    expect(screen.getByText('No se encontraron proyectos coincidentes')).toBeInTheDocument();

    // Clear filters
    const clearBtn = screen.getByRole('button', { name: /Limpiar filtros/i });
    await user.click(clearBtn);

    expect(screen.getByText('Empresa Alfa Telecom')).toBeInTheDocument();
    expect(screen.getByText('Banco Beta Financiero')).toBeInTheDocument();
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

    const detailButtons = screen.getAllByRole('button', { name: /Ver detalle/i });
    await user.click(detailButtons[0]);

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
