import React, { useState, useMemo } from 'react';
import { ProjectArchiveFilter, ProjectRead } from '../../types/projects';
import {
  FolderKanban,
  Plus,
  RefreshCw,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Search,
  X,
  Filter,
} from 'lucide-react';

interface ProjectListProps {
  projects: ProjectRead[];
  isLoading: boolean;
  errorMessage: string | null;
  onRefresh: () => void;
  onSelectProject: (projectId: string) => void;
  onOpenCreateModal: () => void;
  archiveFilter?: ProjectArchiveFilter;
  onArchiveFilterChange?: (filter: ProjectArchiveFilter) => void;
}

type ProjectStatusFilter = 'all' | 'draft' | 'active' | 'archived';

export const ProjectList: React.FC<ProjectListProps> = ({
  projects,
  isLoading,
  errorMessage,
  onRefresh,
  onSelectProject,
  onOpenCreateModal,
  archiveFilter = 'exclude',
  onArchiveFilterChange,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<ProjectStatusFilter>('all');

  const handleStatusFilterChange = (nextStatus: ProjectStatusFilter) => {
    setStatusFilter(nextStatus);
    onArchiveFilterChange?.(nextStatus === 'archived' ? 'only' : 'exclude');
  };

  const handleArchiveFilterChange = (nextArchiveFilter: ProjectArchiveFilter) => {
    onArchiveFilterChange?.(nextArchiveFilter);

    if (nextArchiveFilter === 'only') {
      setStatusFilter('archived');
    } else if (statusFilter === 'archived') {
      setStatusFilter('all');
    }
  };

  // Filtrado reactivo en capa de presentación sin recarga
  const filteredProjects = useMemo(() => {
    return projects.filter((project) => {
      const query = searchTerm.toLowerCase().trim();
      const matchesSearch =
        query === '' ||
        project.company_name.toLowerCase().includes(query) ||
        project.business_need.toLowerCase().includes(query);

      const matchesStatus =
        statusFilter === 'all' ||
        project.status.toLowerCase() === statusFilter.toLowerCase();

      return matchesSearch && matchesStatus;
    });
  }, [projects, searchTerm, statusFilter]);

  const hasActiveFilters =
    searchTerm.trim() !== '' || statusFilter !== 'all' || archiveFilter !== 'exclude';

  const clearFilters = () => {
    setSearchTerm('');
    setStatusFilter('all');
    onArchiveFilterChange?.('exclude');
  };

  return (
    <div className="space-y-6">
      {/* Barra de Herramientas y Encabezado */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-dark-border">
        <div>
          <div className="flex items-center space-x-2">
            <h2 className="text-xl font-bold text-darktext-primary tracking-tight">Proyectos Registrados</h2>
            <span
              data-testid="project-count-badge"
              className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-dark-elevated text-brand-emerald border border-dark-border"
            >
              {hasActiveFilters
                ? `Mostrando ${filteredProjects.length} de ${projects.length}`
                : projects.length}
            </span>
          </div>
          <p className="text-xs text-darktext-secondary mt-0.5">
            Proyectos analíticos gobernados bajo el marco metodológico CRISP-DM
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={onRefresh}
            disabled={isLoading}
            className="inline-flex items-center space-x-1.5 px-3 py-2 text-xs font-medium rounded-lg text-darktext-secondary bg-dark-elevated border border-dark-border hover:text-darktext-primary hover:bg-dark-border disabled:opacity-50 transition-colors shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Actualizar</span>
          </button>

          <button
            type="button"
            onClick={onOpenCreateModal}
            className="inline-flex items-center space-x-1.5 px-3.5 py-2 text-xs font-bold rounded-lg text-dark-primary bg-brand-emerald hover:bg-brand-emeraldHover transition-colors shadow-sm shadow-emerald-950/40"
          >
            <Plus className="w-4 h-4" />
            <span>Nuevo Proyecto</span>
          </button>
        </div>
      </div>

      {/* Controles de Búsqueda y Filtrado */}
      {(projects.length > 0 || archiveFilter !== 'exclude') && (
        <div className="bg-dark-card p-3.5 rounded-xl border border-dark-border shadow-sm flex flex-col sm:flex-row items-center gap-3">
          {/* Buscador Textual */}
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-darktext-secondary" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Buscar por empresa o necesidad de negocio..."
              className="w-full pl-9 pr-8 py-1.5 text-xs rounded-lg border border-dark-border bg-dark-elevated focus:outline-none focus:ring-1 focus:ring-brand-emerald focus:border-brand-emerald text-darktext-primary placeholder-darktext-secondary/50 transition-colors"
              aria-label="Buscar proyectos"
            />
            {searchTerm && (
              <button
                type="button"
                onClick={() => setSearchTerm('')}
                className="absolute right-2.5 top-2 text-darktext-secondary hover:text-darktext-primary"
                aria-label="Limpiar búsqueda"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Filtro por Estado (Contratos Reales) */}
          <div className="flex items-center space-x-2 w-full sm:w-auto">
            <Filter className="w-3.5 h-3.5 text-darktext-secondary flex-shrink-0" />
            <select
              value={statusFilter}
              onChange={(e) => handleStatusFilterChange(e.target.value as ProjectStatusFilter)}
              className="text-xs rounded-lg border border-dark-border py-1.5 px-2.5 bg-dark-elevated text-darktext-primary focus:outline-none focus:ring-1 focus:ring-brand-emerald"
              aria-label="Filtrar por estado"
            >
              <option value="all">Todos los estados</option>
              <option value="draft">Borrador (draft)</option>
              <option value="active">Activo (active)</option>
              <option value="archived">Archivado (archived)</option>
            </select>

            <select
              value={archiveFilter}
              onChange={(e) => handleArchiveFilterChange(e.target.value as ProjectArchiveFilter)}
              className="text-xs rounded-lg border border-dark-border py-1.5 px-2.5 bg-dark-elevated text-darktext-primary focus:outline-none focus:ring-1 focus:ring-brand-emerald"
              aria-label="Filtrar por archivado"
            >
              <option value="exclude">Activos y borradores</option>
              <option value="only">Solo archivados</option>
              <option value="include">Incluir archivados</option>
            </select>

            {hasActiveFilters && (
              <button
                type="button"
                onClick={clearFilters}
                className="px-2 py-1.5 text-[11px] font-semibold text-darktext-secondary hover:text-darktext-primary hover:bg-dark-elevated rounded-lg transition-colors flex-shrink-0"
              >
                Limpiar
              </button>
            )}
          </div>
        </div>
      )}

      {/* Estado de Error */}
      {errorMessage && (
        <div
          data-testid="project-list-error"
          className="bg-rose-950/30 border border-brand-error/40 rounded-xl p-4 text-xs text-darktext-primary flex items-start justify-between"
        >
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-brand-error flex-shrink-0" />
            <div>
              <p className="font-semibold text-brand-error">Error al cargar la lista de proyectos</p>
              <p className="font-mono mt-0.5 text-rose-300">{errorMessage}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onRefresh}
            className="px-2.5 py-1 text-xs font-semibold rounded bg-rose-900/60 text-brand-error border border-rose-700/60 hover:bg-rose-900 transition-colors"
          >
            Reintentar
          </button>
        </div>
      )}

      {/* Estado de Carga */}
      {isLoading && (
        <div data-testid="project-list-loading" className="py-12 flex flex-col items-center justify-center text-darktext-secondary space-y-3">
          <RefreshCw className="w-6 h-6 animate-spin text-brand-emerald" />
          <span className="text-xs">Consultando proyectos en la API...</span>
        </div>
      )}

      {/* Estado Vacío Total (Sin proyectos en el backend) */}
      {!isLoading && !errorMessage && projects.length === 0 && archiveFilter === 'exclude' && (
        <div
          data-testid="project-list-empty"
          className="bg-dark-card border border-dashed border-dark-border rounded-xl p-12 text-center max-w-lg mx-auto space-y-4 shadow-sm"
        >
          <div className="w-12 h-12 rounded-full bg-dark-elevated border border-dark-border text-brand-emerald mx-auto flex items-center justify-center">
            <FolderKanban className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-darktext-primary">No hay proyectos registrados aún</h3>
            <p className="text-xs text-darktext-secondary">
              Registra tu primer proyecto analítico definiendo empresa, necesidad de negocio y criterios de éxito.
            </p>
          </div>
          <button
            type="button"
            onClick={onOpenCreateModal}
            className="inline-flex items-center space-x-1.5 px-4 py-2 text-xs font-bold rounded-lg text-dark-primary bg-brand-emerald hover:bg-brand-emeraldHover transition-colors shadow-sm shadow-emerald-950/40"
          >
            <Plus className="w-4 h-4" />
            <span>Crear Primer Proyecto</span>
          </button>
        </div>
      )}

      {!isLoading && !errorMessage && projects.length === 0 && archiveFilter !== 'exclude' && (
        <div
          data-testid="project-list-filtered-empty"
          className="bg-dark-card border border-dashed border-dark-border rounded-xl p-8 text-center max-w-md mx-auto space-y-3 text-xs"
        >
          <FolderKanban className="w-8 h-8 text-darktext-secondary mx-auto" />
          <div>
            <h4 className="font-semibold text-darktext-primary text-sm">
              No se encontraron proyectos archivados
            </h4>
            <p className="text-darktext-secondary mt-1">
              Cambia el filtro para volver a consultar los proyectos activos y borradores.
            </p>
          </div>
          <button
            type="button"
            onClick={clearFilters}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-dark-elevated text-brand-emerald hover:bg-dark-border border border-dark-border transition-colors"
          >
            Volver a proyectos activos
          </button>
        </div>
      )}

      {/* Estado Vacío por Filtrado (Proyectos existen pero ninguno coincide) */}
      {!isLoading && !errorMessage && projects.length > 0 && filteredProjects.length === 0 && (
        <div
          data-testid="project-list-filtered-empty"
          className="bg-dark-card border border-dashed border-dark-border rounded-xl p-8 text-center max-w-md mx-auto space-y-3 text-xs"
        >
          <Search className="w-8 h-8 text-darktext-secondary mx-auto" />
          <div>
            <h4 className="font-semibold text-darktext-primary text-sm">
              No se encontraron proyectos coincidentes
            </h4>
            <p className="text-darktext-secondary mt-1">
              No hay proyectos que correspondan con los criterios de búsqueda o filtros seleccionados.
            </p>
          </div>
          <button
            type="button"
            onClick={clearFilters}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-dark-elevated text-brand-emerald hover:bg-dark-border border border-dark-border transition-colors"
          >
            Limpiar filtros de búsqueda
          </button>
        </div>
      )}

      {/* Tabla / Lista de Proyectos Filtrados */}
      {!isLoading && filteredProjects.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredProjects.map((project) => (
            <div
              key={project.id}
              data-testid={`project-card-${project.id}`}
              className="bg-dark-card border border-dark-border hover:border-brand-emerald/50 rounded-xl p-5 shadow-sm hover:shadow-lg hover:shadow-black/40 transition-all flex flex-col justify-between group"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="font-bold text-darktext-primary text-sm tracking-tight leading-snug group-hover:text-brand-emerald transition-colors">
                    {project.company_name}
                  </h3>
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold capitalize flex-shrink-0 border ${
                    project.status === 'active'
                      ? 'bg-emerald-950/70 text-brand-emerald border-emerald-700/50'
                      : project.status === 'archived'
                      ? 'bg-amber-950/70 text-brand-warning border-amber-700/50'
                      : 'bg-dark-elevated text-darktext-secondary border-dark-border'
                  }`}>
                    {project.status}
                  </span>
                </div>

                <p className="text-xs text-darktext-secondary line-clamp-2 leading-relaxed">
                  {project.business_need}
                </p>

                <div className="space-y-1.5 pt-2 border-t border-dark-border/60 text-xs">
                  <div className="flex items-center justify-between text-darktext-secondary">
                    <span>Fase CRISP-DM:</span>
                    <span className="font-medium text-brand-turquoise font-mono text-[11px]">
                      {project.current_phase}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-darktext-secondary">
                    <span>Criterios de éxito:</span>
                    <span className="font-semibold text-brand-emerald">
                      {project.success_criteria.length} definidos
                    </span>
                  </div>
                </div>

                {project.success_criteria.length > 0 && (
                  <div className="bg-dark-elevated p-2.5 rounded-lg border border-dark-border/60 space-y-1">
                    <span className="text-[10px] uppercase tracking-wider font-semibold text-darktext-secondary/70 block">
                      Criterio principal:
                    </span>
                    <p className="text-xs text-darktext-primary truncate flex items-center space-x-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-brand-emerald flex-shrink-0" />
                      <span className="truncate">{project.success_criteria[0]}</span>
                    </p>
                  </div>
                )}
              </div>

              <div className="pt-4 mt-4 border-t border-dark-border/60 flex items-center justify-between">
                <span className="text-[11px] text-darktext-secondary flex items-center space-x-1">
                  <Clock className="w-3 h-3" />
                  <span>{new Date(project.created_at).toLocaleDateString()}</span>
                </span>

                <button
                  type="button"
                  onClick={() => onSelectProject(project.id)}
                  className="inline-flex items-center space-x-1 text-xs font-semibold text-brand-emerald hover:text-brand-turquoise px-2 py-1 rounded bg-dark-elevated/80 border border-dark-border/60 hover:border-brand-emerald/40 transition-colors"
                >
                  <span>Ver detalle</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
