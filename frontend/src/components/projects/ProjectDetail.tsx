import React, { useState, useEffect, useCallback } from 'react';
import { ProjectRead } from '../../types/projects';
import { getProject } from '../../api/projects';
import {
  ArrowLeft,
  Copy,
  Check,
  RefreshCw,
  AlertTriangle,
  Building2,
  Target,
  FileText,
  Shield,
  Layers,
  Sparkles,
  Calendar,
  User,
} from 'lucide-react';

interface ProjectDetailProps {
  projectId: string;
  onBack: () => void;
}

export const ProjectDetail: React.FC<ProjectDetailProps> = ({ projectId, onBack }) => {
  const [project, setProject] = useState<ProjectRead | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState(false);

  const fetchProject = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const data = await getProject(projectId);
      setProject(data);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('Error al consultar el detalle del proyecto');
      }
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchProject();
  }, [fetchProject]);

  const handleCopyId = async () => {
    if (!project?.id) return;
    try {
      await navigator.clipboard.writeText(project.id);
      setCopiedId(true);
      setTimeout(() => setCopiedId(false), 2000);
    } catch {
      // Fallback
    }
  };

  if (isLoading) {
    return (
      <div data-testid="project-detail-loading" className="py-20 flex flex-col items-center justify-center space-y-3 text-slate-500">
        <RefreshCw className="w-8 h-8 animate-spin text-emerald-600" />
        <span className="text-xs">Cargando ficha del proyecto...</span>
      </div>
    );
  }

  if (errorMessage || !project) {
    return (
      <div data-testid="project-detail-error" className="bg-rose-50 border border-rose-200 rounded-xl p-6 text-center max-w-lg mx-auto space-y-4">
        <div className="w-10 h-10 rounded-full bg-rose-100 text-rose-600 mx-auto flex items-center justify-center">
          <AlertTriangle className="w-5 h-5" />
        </div>
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-rose-900">No se pudo cargar el proyecto</h3>
          <p className="text-xs text-rose-700 font-mono">{errorMessage || 'Proyecto no encontrado'}</p>
        </div>
        <div className="flex justify-center space-x-3 pt-2">
          <button
            type="button"
            onClick={onBack}
            className="px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-white border border-slate-300 text-slate-700 hover:bg-slate-50 transition-colors"
          >
            Volver a la lista
          </button>
          <button
            type="button"
            onClick={fetchProject}
            className="px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-rose-600 text-white hover:bg-rose-700 transition-colors shadow-sm"
          >
            Reintentar
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Navegación y Barra de Estado Superior */}
      <div className="flex items-center justify-between pb-4 border-b border-slate-200">
        <div className="flex items-center space-x-3">
          <button
            type="button"
            onClick={onBack}
            className="p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors"
            aria-label="Volver a la lista de proyectos"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-medium text-emerald-700 uppercase tracking-wider">
                Ficha del Proyecto
              </span>
              <span className="text-slate-300">&bull;</span>
              <span className="text-xs text-slate-500">M1: Negocio</span>
            </div>
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              {project.company_name}
            </h1>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 capitalize">
            {project.status}
          </span>
          <button
            type="button"
            onClick={fetchProject}
            disabled={isLoading}
            className="p-2 rounded-lg text-slate-500 hover:text-slate-700 hover:bg-slate-100 transition-colors"
            title="Refrescar ficha"
            aria-label="Refrescar ficha"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Identificador y Metadatos de Cabecera */}
      <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
        <div>
          <span className="text-slate-400 block text-[11px] mb-1 font-medium">Project ID</span>
          <div className="flex items-center space-x-1.5 font-mono text-slate-800 bg-slate-50 px-2 py-1 rounded border border-slate-200">
            <span className="truncate" title={project.id}>{project.id}</span>
            <button
              type="button"
              onClick={handleCopyId}
              className="text-slate-500 hover:text-emerald-600 transition-colors flex-shrink-0"
              aria-label="Copiar ID del proyecto"
              title="Copiar ID"
            >
              {copiedId ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>

        <div>
          <span className="text-slate-400 block text-[11px] mb-1 font-medium">Fase Actual CRISP-DM</span>
          <span className="inline-flex items-center space-x-1.5 font-semibold text-slate-800 bg-slate-50 px-2 py-1 rounded border border-slate-200">
            <Layers className="w-3.5 h-3.5 text-blue-600" />
            <span className="font-mono text-[11px]">{project.current_phase}</span>
          </span>
        </div>

        <div>
          <span className="text-slate-400 block text-[11px] mb-1 font-medium">Registro y Responsable</span>
          <div className="flex items-center justify-between text-slate-700 bg-slate-50 px-2 py-1 rounded border border-slate-200">
            <span className="flex items-center space-x-1">
              <Calendar className="w-3 h-3 text-slate-400" />
              <span>{new Date(project.created_at).toLocaleDateString()}</span>
            </span>
            {project.owner_id && (
              <span className="flex items-center space-x-1 text-slate-600 font-mono text-[11px]">
                <User className="w-3 h-3 text-slate-400" />
                <span>{project.owner_id}</span>
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Secciones del Problema y Entendimiento de Negocio */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Columna Izquierda: Definición del Problema */}
        <div className="space-y-6">
          {/* Descripción de la Empresa */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-2">
            <h3 className="font-semibold text-slate-900 text-xs flex items-center space-x-2">
              <Building2 className="w-4 h-4 text-emerald-600" />
              <span>Descripción de la Empresa</span>
            </h3>
            <p className="text-xs text-slate-700 leading-relaxed whitespace-pre-line bg-slate-50/50 p-3 rounded-lg border border-slate-100">
              {project.company_description}
            </p>
          </div>

          {/* Necesidad de Negocio */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-2">
            <h3 className="font-semibold text-slate-900 text-xs flex items-center space-x-2">
              <Target className="w-4 h-4 text-blue-600" />
              <span>Necesidad o Problema de Negocio</span>
            </h3>
            <p className="text-xs text-slate-700 leading-relaxed whitespace-pre-line bg-slate-50/50 p-3 rounded-lg border border-slate-100">
              {project.business_need}
            </p>
          </div>

          {/* Objetivo Esperado */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-2">
            <h3 className="font-semibold text-slate-900 text-xs flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-amber-600" />
              <span>Objetivo Analítico Esperado</span>
            </h3>
            <p className="text-xs text-slate-700 leading-relaxed whitespace-pre-line bg-slate-50/50 p-3 rounded-lg border border-slate-100">
              {project.expected_objective}
            </p>
          </div>
        </div>

        {/* Columna Derecha: Criterios, Reglas y Restricciones */}
        <div className="space-y-6">
          {/* Criterios de Éxito */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-slate-900 text-xs flex items-center space-x-2">
                <Check className="w-4 h-4 text-emerald-600" />
                <span>Criterios de Éxito Verificables</span>
              </h3>
              <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                {project.success_criteria.length} definidos
              </span>
            </div>

            <ul className="space-y-2 text-xs">
              {project.success_criteria.map((criterion, index) => (
                <li
                  key={index}
                  className="flex items-start space-x-2 bg-emerald-50/40 border border-emerald-100 p-2.5 rounded-lg text-slate-800"
                >
                  <span className="w-4 h-4 rounded-full bg-emerald-100 text-emerald-700 font-mono text-[10px] flex items-center justify-center flex-shrink-0 mt-0.5 font-bold">
                    {index + 1}
                  </span>
                  <span className="leading-relaxed">{criterion}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Reglas de Negocio */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-slate-900 text-xs flex items-center space-x-2">
                <Shield className="w-4 h-4 text-slate-700" />
                <span>Reglas de Negocio</span>
              </h3>
              <span className="text-[11px] text-slate-500 font-medium">
                {project.business_rules.length} declaradas
              </span>
            </div>

            {project.business_rules.length === 0 ? (
              <p className="text-xs text-slate-400 italic">No se declararon reglas de negocio adicionales.</p>
            ) : (
              <ul className="space-y-1.5 text-xs">
                {project.business_rules.map((rule, index) => (
                  <li
                    key={index}
                    className="flex items-start space-x-2 bg-slate-50 border border-slate-100 p-2 rounded-lg text-slate-700"
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-slate-400 mt-1.5 flex-shrink-0"></span>
                    <span>{rule}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Restricciones */}
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-slate-900 text-xs flex items-center space-x-2">
                <FileText className="w-4 h-4 text-slate-700" />
                <span>Restricciones del Proyecto</span>
              </h3>
              <span className="text-[11px] text-slate-500 font-medium">
                {project.constraints.length} declaradas
              </span>
            </div>

            {project.constraints.length === 0 ? (
              <p className="text-xs text-slate-400 italic">No se declararon restricciones adicionales.</p>
            ) : (
              <ul className="space-y-1.5 text-xs">
                {project.constraints.map((constraint, index) => (
                  <li
                    key={index}
                    className="flex items-start space-x-2 bg-slate-50 border border-slate-100 p-2 rounded-lg text-slate-700"
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-slate-400 mt-1.5 flex-shrink-0"></span>
                    <span>{constraint}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>

      {/* Próximos Pasos en el Ciclo de Vida */}
      <div className="bg-slate-900 text-slate-200 rounded-xl p-5 shadow-sm space-y-3 text-xs">
        <div className="flex items-center space-x-2 text-slate-100 font-bold">
          <Layers className="w-4 h-4 text-emerald-400" />
          <span>Siguiente Etapa del Ciclo Metodológico</span>
        </div>
        <p className="text-slate-400 leading-relaxed">
          Este proyecto ha completado el registro inicial deentendimiento del negocio. Las siguientes
          capacidades habilitadas en el flujo analítico son:
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
          <div className="p-3 bg-slate-800/80 rounded-lg border border-slate-700">
            <span className="font-semibold text-emerald-400 block mb-1">M11.3B: Instantáneas de Contexto</span>
            <span className="text-[11px] text-slate-400">
              Evolución inmutable del entendimiento mediante versiones append-only selladas criptográficamente.
            </span>
          </div>
          <div className="p-3 bg-slate-800/80 rounded-lg border border-slate-700">
            <span className="font-semibold text-emerald-400 block mb-1">M11.4: Ingesta Bronze y Datos</span>
            <span className="text-[11px] text-slate-400">
              Carga del dataset CSV crudo y perfilado exploratorio automatizado.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
