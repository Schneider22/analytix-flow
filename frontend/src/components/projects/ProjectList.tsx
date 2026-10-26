import React, { useState, useMemo } from 'react';
import { ProjectRead } from '../../types/projects';
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
}

export const ProjectList: React.FC<ProjectListProps> = ({
  projects,
  isLoading,
  errorMessage,
  onRefresh,
  onSelectProject,
  onOpenCreateModal,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'draft' | 'active' | 'archived'>('all');

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

  const hasActiveFilters = searchTerm.trim() !== '' || statusFilter !== 'all';

  const clearFilters = () => {
    setSearchTerm('');
    setStatusFilter('all');
  };

  return (
    <div className="space-y-6">
      {/* Barra de Herramientas y Encabezado */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center space-x-2">
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">Proyectos Registrados</h2>
            <span
              data-testid="project-count-badge"
              className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800"
            >
              {hasActiveFilters
                ? `Mostrando ${filteredProjects.length} de ${projects.length}`
                : projects.length}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Proyectos analíticos gobernados bajo el marco metodológico CRISP-DM
          </p>
        </div>

        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={onRefresh}
            disabled={isLoading}
            className="inline-flex items-center space-x-1.5 px-3 py-2 text-xs font-medium rounded-lg text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 disabled:opacity-50 transition-colors shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            <span>Actualizar</span>
          </button>

          <button
            type="button"
            onClick={onOpenCreateModal}
            className="inline-flex items-center space-x-1.5 px-3.5 py-2 text-xs font-semibold rounded-lg text-white bg-emerald-600 hover:bg-emerald-700 transition-colors shadow-sm"
          >
            <Plus className="w-4 h-4" />
            <span>Nuevo Proyecto</span>
          </button>
        </div>
      </div>

      {/* Controles de Búsqueda y Filtrado */}
      {projects.length > 0 && (
        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs flex flex-col sm:flex-row items-center gap-3">
          {/* Buscador Textual */}
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Buscar por empresa o necesidad de negocio..."
              className="w-full pl-9 pr-8 py-1.5 text-xs rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-500 text-slate-800 placeholder-slate-400"
              aria-label="Buscar proyectos"
            />
            {searchTerm && (
              <button
                type="button"
                onClick={() => setSearchTerm('')}
                className="absolute right-2.5 top-2 text-slate-400 hover:text-slate-600"
                aria-label="Limpiar búsqueda"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Filtro por Estado (Contratos Reales) */}
          <div className="flex items-center space-x-2 w-full sm:w-auto">
            <Filter className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
            <select
              value={statusFilter}
              onChange={(e) =>
                setStatusFilter(e.target.value as 'all' | 'draft' | 'active' | 'archived')
              }
              className="text-xs rounded-lg border border-slate-300 py-1.5 px-2.5 bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              aria-label="Filtrar por estado"
            >
              <option value="all">Todos los estados</option>
              <option value="draft">Borrador (draft)</option>
              <option value="active">Activo (active)</option>
              <option value="archived">Archivado (archived)</option>
            </select>

            {hasActiveFilters && (
              <button
                type="button"
                onClick={clearFilters}
                className="px-2 py-1.5 text-[11px] font-semibold text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors flex-shrink-0"
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
          className="bg-rose-50 border border-rose-200 rounded-xl p-4 text-xs text-rose-800 flex items-start justify-between"
        >
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" />
            <div>
              <p className="font-semibold">Error al cargar la lista de proyectos</p>
              <p className="font-mono mt-0.5 text-rose-700">{errorMessage}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onRefresh}
            className="px-2.5 py-1 text-xs font-medium rounded bg-rose-100 text-rose-800 hover:bg-rose-200 transition-colors"
          >
            Reintentar
          </button>
        </div>
      )}

      {/* Estado de Carga */}
      {isLoading && (
        <div data-testid="project-list-loading" className="py-12 flex flex-col items-center justify-center text-slate-500 space-y-3">
          <RefreshCw className="w-6 h-6 animate-spin text-emerald-600" />
          <span className="text-xs">Consultando proyectos en la API...</span>
        </div>
      )}

      {/* Estado Vacío Total (Sin proyectos en el backend) */}
      {!isLoading && !errorMessage && projects.length === 0 && (
        <div
          data-testid="project-list-empty"
          className="bg-white border border-dashed border-slate-300 rounded-xl p-12 text-center max-w-lg mx-auto space-y-4"
        >
          <div className="w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 mx-auto flex items-center justify-center">
            <FolderKanban className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-slate-800">No hay proyectos registrados aún</h3>
            <p className="text-xs text-slate-500">
              Registra tu primer proyecto analítico definiendo empresa, necesidad de negocio y criterios de éxito.
            </p>
          </div>
          <button
            type="button"
            onClick={onOpenCreateModal}
            className="inline-flex items-center space-x-1.5 px-4 py-2 text-xs font-semibold rounded-lg text-white bg-emerald-600 hover:bg-emerald-700 transition-colors shadow-sm"
          >
            <Plus className="w-4 h-4" />
            <span>Crear Primer Proyecto</span>
          </button>
        </div>
      )}

      {/* Estado Vacío por Filtrado (Proyectos existen pero ninguno coincide) */}
      {!isLoading && !errorMessage && projects.length > 0 && filteredProjects.length === 0 && (
        <div
          data-testid="project-list-filtered-empty"
          className="bg-white border border-dashed border-slate-300 rounded-xl p-8 text-center max-w-md mx-auto space-y-3 text-xs"
        >
          <Search className="w-8 h-8 text-slate-300 mx-auto" />
          <div>
            <h4 className="font-semibold text-slate-800 text-sm">
              No se encontraron proyectos coincidentes
            </h4>
            <p className="text-slate-500 mt-1">
              No hay proyectos que correspondan con los criterios de búsqueda o filtros seleccionados.
            </p>
          </div>
          <button
            type="button"
            onClick={clearFilters}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200 transition-colors"
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
              className="bg-white border border-slate-200 hover:border-emerald-300 rounded-xl p-5 shadow-sm hover:shadow transition-all flex flex-col justify-between"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="font-bold text-slate-900 text-sm tracking-tight leading-snug">
                    {project.company_name}
                  </h3>
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700 border border-slate-200 capitalize flex-shrink-0">
                    {project.status}
                  </span>
                </div>

                <p className="text-xs text-slate-600 line-clamp-2">
                  {project.business_need}
                </p>

                <div className="space-y-1.5 pt-2 border-t border-slate-100 text-xs">
                  <div className="flex items-center justify-between text-slate-500">
                    <span>Fase CRISP-DM:</span>
                    <span className="font-medium text-slate-800 font-mono text-[11px]">
                      {project.current_phase}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-slate-500">
                    <span>Criterios de éxito:</span>
                    <span className="font-semibold text-emerald-700">
                      {project.success_criteria.length} definidos
                    </span>
                  </div>
                </div>

                {project.success_criteria.length > 0 && (
                  <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100 space-y-1">
                    <span className="text-[10px] uppercase tracking-wider font-semibold text-slate-400 block">
                      Criterio principal:
                    </span>
                    <p className="text-xs text-slate-700 truncate flex items-center space-x-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
                      <span className="truncate">{project.success_criteria[0]}</span>
                    </p>
                  </div>
                )}
              </div>

              <div className="pt-4 mt-4 border-t border-slate-100 flex items-center justify-between">
                <span className="text-[11px] text-slate-400 flex items-center space-x-1">
                  <Clock className="w-3 h-3" />
                  <span>{new Date(project.created_at).toLocaleDateString()}</span>
                </span>

                <button
                  type="button"
                  onClick={() => onSelectProject(project.id)}
                  className="inline-flex items-center space-x-1 text-xs font-semibold text-emerald-700 hover:text-emerald-800 p-1 rounded hover:bg-emerald-50 transition-colors"
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
