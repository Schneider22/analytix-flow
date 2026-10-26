import React from 'react';
import { ProjectRead } from '../../types/projects';
import { FolderKanban, Plus, RefreshCw, AlertTriangle, ArrowRight, CheckCircle2, Clock } from 'lucide-react';

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
              {projects.length}
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

      {/* Estado Vacío */}
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

      {/* Tabla / Lista de Proyectos */}
      {!isLoading && projects.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {projects.map((project) => (
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
