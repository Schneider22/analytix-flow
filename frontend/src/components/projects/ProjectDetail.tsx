import React, { useState, useEffect, useCallback, useRef } from 'react';
import { ProjectRead, ContextRead, DecisionRead, AuditEventRead } from '../../types/projects';
import { archiveProject, getProject, restoreProject } from '../../api/projects';
import { listContextSnapshots } from '../../api/context';
import { listDecisions } from '../../api/decisions';
import { listAuditEvents } from '../../api/audit';
import { ContextTimeline } from './ContextTimeline';
import { DecisionList } from './DecisionList';
import { AlternativesMatrix } from './AlternativesMatrix';
import { AuditTrailView } from './AuditTrailView';
import { ProjectLifecycleAction, ProjectLifecycleModal } from './ProjectLifecycleModal';
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
  History,
  Scale,
  ShieldCheck,
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
  const [lifecycleAction, setLifecycleAction] = useState<ProjectLifecycleAction | null>(null);
  const [isLifecycleSubmitting, setIsLifecycleSubmitting] = useState(false);
  const [lifecycleError, setLifecycleError] = useState<string | null>(null);
  const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Limpieza del temporizador al desmontar el componente
  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) {
        clearTimeout(copyTimeoutRef.current);
      }
    };
  }, []);

  // Pestaña Activa: 'general' | 'context' | 'decisions' | 'alternatives' | 'audit'
  const [activeTab, setActiveTab] = useState<'general' | 'context' | 'decisions' | 'alternatives' | 'audit'>(
    'general'
  );

  // Estado de Instantáneas de Contexto
  const [snapshots, setSnapshots] = useState<ContextRead[]>([]);
  const [isLoadingSnapshots, setIsLoadingSnapshots] = useState(false);
  const [snapshotsError, setSnapshotsError] = useState<string | null>(null);

  // Estado de Decisiones de Negocio
  const [decisions, setDecisions] = useState<DecisionRead[]>([]);
  const [isLoadingDecisions, setIsLoadingDecisions] = useState(false);
  const [decisionsError, setDecisionsError] = useState<string | null>(null);

  // Estado de Pista de Auditoría
  const [auditEvents, setAuditEvents] = useState<AuditEventRead[]>([]);
  const [isLoadingAudit, setIsLoadingAudit] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);

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

  const fetchSnapshots = useCallback(async () => {
    setIsLoadingSnapshots(true);
    setSnapshotsError(null);
    try {
      const data = await listContextSnapshots(projectId);
      setSnapshots(data);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setSnapshotsError(err.message);
      } else {
        setSnapshotsError('Error al consultar las instantáneas de contexto');
      }
    } finally {
      setIsLoadingSnapshots(false);
    }
  }, [projectId]);

  const fetchDecisions = useCallback(async () => {
    setIsLoadingDecisions(true);
    setDecisionsError(null);
    try {
      const data = await listDecisions(projectId);
      setDecisions(data);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setDecisionsError(err.message);
      } else {
        setDecisionsError('Error al consultar las decisiones de negocio');
      }
    } finally {
      setIsLoadingDecisions(false);
    }
  }, [projectId]);

  const fetchAuditEvents = useCallback(async () => {
    setIsLoadingAudit(true);
    setAuditError(null);
    try {
      const data = await listAuditEvents(projectId);
      setAuditEvents(data);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setAuditError(err.message);
      } else {
        setAuditError('Error al consultar la pista de auditoría');
      }
    } finally {
      setIsLoadingAudit(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchProject();
    fetchSnapshots();
    fetchDecisions();
    fetchAuditEvents();
  }, [fetchProject, fetchSnapshots, fetchDecisions, fetchAuditEvents]);

  const handleCopyId = async () => {
    if (!project?.id) return;
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(project.id);
      }
      if (copyTimeoutRef.current) {
        clearTimeout(copyTimeoutRef.current);
      }
      setCopiedId(true);
      copyTimeoutRef.current = setTimeout(() => {
        setCopiedId(false);
        copyTimeoutRef.current = null;
      }, 2000);
    } catch {
      // Fallback
    }
  };

  const handleRefreshAll = () => {
    fetchProject();
    fetchSnapshots();
    fetchDecisions();
    fetchAuditEvents();
  };

  const handleSnapshotCreated = (newSnapshot: ContextRead) => {
    setSnapshots((prev) => [...prev, newSnapshot]);
    fetchAuditEvents();
  };

  const handleDecisionCreated = (newDecision: DecisionRead) => {
    setDecisions((prev) => [newDecision, ...prev]);
    fetchAuditEvents();
  };

  const handleLifecycleSubmit = async (payload: { actor_id: string; reason?: string }) => {
    if (!project || !lifecycleAction) return;
    setIsLifecycleSubmitting(true);
    setLifecycleError(null);
    try {
      const updatedProject = lifecycleAction === 'archive'
        ? await archiveProject(project.id, { actor_id: payload.actor_id, reason: payload.reason ?? '' })
        : await restoreProject(project.id, payload);
      setProject(updatedProject);
      setLifecycleAction(null);
      fetchAuditEvents();
    } catch (err: unknown) {
      setLifecycleError(err instanceof Error ? err.message : 'No se pudo actualizar el estado del proyecto');
    } finally {
      setIsLifecycleSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div data-testid="project-detail-loading" className="py-20 flex flex-col items-center justify-center space-y-3 text-darktext-secondary">
        <RefreshCw className="w-8 h-8 animate-spin text-brand-emerald" />
        <span className="text-xs">Cargando ficha del proyecto...</span>
      </div>
    );
  }

  if (errorMessage || !project) {
    return (
      <div data-testid="project-detail-error" className="bg-rose-950/30 border border-brand-error/40 rounded-xl p-6 text-center max-w-lg mx-auto space-y-4 shadow-lg">
        <div className="w-10 h-10 rounded-full bg-rose-900/50 border border-rose-700/50 text-brand-error mx-auto flex items-center justify-center">
          <AlertTriangle className="w-5 h-5" />
        </div>
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-brand-error">No se pudo cargar el proyecto</h3>
          <p className="text-xs text-rose-300 font-mono">{errorMessage || 'Proyecto no encontrado'}</p>
        </div>
        <div className="flex justify-center space-x-3 pt-2">
          <button
            type="button"
            onClick={onBack}
            className="px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-dark-elevated border border-dark-border text-darktext-primary hover:bg-dark-border transition-colors"
          >
            Volver a la lista
          </button>
          <button
            type="button"
            onClick={handleRefreshAll}
            className="px-3.5 py-1.5 text-xs font-bold rounded-lg bg-brand-emerald text-dark-primary hover:bg-brand-emeraldHover transition-colors shadow-sm"
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
      <div className="flex items-center justify-between pb-4 border-b border-dark-border">
        <div className="flex items-center space-x-3">
          <button
            type="button"
            onClick={onBack}
            className="p-2 rounded-lg text-darktext-secondary hover:text-darktext-primary hover:bg-dark-elevated transition-colors"
            aria-label="Volver a la lista de proyectos"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-semibold text-brand-emerald uppercase tracking-wider">
                Ficha del Proyecto
              </span>
              <span className="text-darktext-secondary/50">&bull;</span>
              <span className="text-xs text-brand-turquoise">M1: Entendimiento de Negocio</span>
            </div>
            <h1 className="text-xl font-bold text-darktext-primary tracking-tight">
              {project.company_name}
            </h1>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold capitalize border ${
            project.status === 'active'
              ? 'bg-emerald-950/70 text-brand-emerald border-emerald-700/50'
              : project.status === 'archived'
              ? 'bg-amber-950/70 text-brand-warning border-amber-700/50'
              : 'bg-dark-elevated text-darktext-secondary border-dark-border'
          }`}>
            {project.status}
          </span>
          <button
            type="button"
            onClick={() => {
              setLifecycleError(null);
              setLifecycleAction(project.status === 'archived' ? 'restore' : 'archive');
            }}
            className={`rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors ${
              project.status === 'archived'
                ? 'border-brand-emerald/50 bg-emerald-950/60 text-brand-emerald hover:bg-emerald-900/70'
                : 'border-amber-700/50 bg-amber-950/60 text-brand-warning hover:bg-amber-900/70'
            }`}
          >
            {project.status === 'archived' ? 'Restaurar' : 'Archivar'}
          </button>
          <button
            type="button"
            onClick={handleRefreshAll}
            disabled={isLoading || isLoadingSnapshots || isLoadingDecisions || isLoadingAudit}
            className="p-2 rounded-lg text-darktext-secondary hover:text-darktext-primary hover:bg-dark-elevated transition-colors"
            title="Refrescar proyecto y módulos"
            aria-label="Refrescar ficha"
          >
            <RefreshCw
              className={`w-4 h-4 ${
                isLoading || isLoadingSnapshots || isLoadingDecisions || isLoadingAudit ? 'animate-spin' : ''
              }`}
            />
          </button>
        </div>
      </div>

      {/* Identificador y Metadatos de Cabecera */}
      <div className="bg-dark-card border border-dark-border rounded-xl p-4 shadow-sm grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
        <div>
          <span className="text-darktext-secondary block text-[11px] mb-1 font-medium">Project ID</span>
          <div className="flex items-center space-x-1.5 font-mono text-darktext-primary bg-dark-elevated px-2 py-1 rounded border border-dark-border">
            <span className="truncate" title={project.id}>{project.id}</span>
            <button
              type="button"
              onClick={handleCopyId}
              className="text-darktext-secondary hover:text-brand-emerald transition-colors flex-shrink-0"
              aria-label="Copiar ID del proyecto"
              title="Copiar ID"
            >
              {copiedId ? <Check className="w-3.5 h-3.5 text-brand-emerald" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>

        <div>
          <span className="text-darktext-secondary block text-[11px] mb-1 font-medium">Fase Actual CRISP-DM</span>
          <span className="inline-flex items-center space-x-1.5 font-semibold text-brand-turquoise bg-dark-elevated px-2 py-1 rounded border border-dark-border">
            <Layers className="w-3.5 h-3.5 text-brand-turquoise" />
            <span className="font-mono text-[11px]">{project.current_phase}</span>
          </span>
        </div>

        <div>
          <span className="text-darktext-secondary block text-[11px] mb-1 font-medium">Registro y Responsable</span>
          <div className="flex items-center justify-between text-darktext-primary bg-dark-elevated px-2 py-1 rounded border border-dark-border">
            <span className="flex items-center space-x-1">
              <Calendar className="w-3 h-3 text-darktext-secondary" />
              <span>{new Date(project.created_at).toLocaleDateString()}</span>
            </span>
            {project.owner_id && (
              <span className="flex items-center space-x-1 text-brand-emerald font-mono text-[11px]">
                <User className="w-3 h-3 text-darktext-secondary" />
                <span>{project.owner_id}</span>
              </span>
            )}
          </div>
        </div>
      </div>

      {project.status === 'archived' && (
        <div className="rounded-xl border border-amber-700/50 bg-amber-950/30 px-4 py-3 text-xs text-amber-100">
          <strong className="font-semibold text-brand-warning">Proyecto archivado.</strong>{' '}
          Consulta histórica habilitada; las operaciones mutantes están bloqueadas.
          {project.archived_at && (
            <span className="ml-1 text-amber-200/80">Archivado el {new Date(project.archived_at).toLocaleString()}</span>
          )}
        </div>
      )}

      {/* Pestañas de Navegación de Módulo */}
      <div className="border-b border-dark-border overflow-x-auto">
        <nav className="flex space-x-4 -mb-px min-w-max" aria-label="Pestañas de la Ficha">
          <button
            type="button"
            onClick={() => setActiveTab('general')}
            className={`inline-flex items-center space-x-2 py-3 px-1 border-b-2 font-medium text-xs transition-colors ${
              activeTab === 'general'
                ? 'border-brand-emerald text-brand-emerald font-semibold'
                : 'border-transparent text-darktext-secondary hover:text-darktext-primary hover:border-dark-border'
            }`}
          >
            <FileText className="w-4 h-4" />
            <span>Ficha General</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('context')}
            className={`inline-flex items-center space-x-2 py-3 px-1 border-b-2 font-medium text-xs transition-colors ${
              activeTab === 'context'
                ? 'border-brand-emerald text-brand-emerald font-semibold'
                : 'border-transparent text-darktext-secondary hover:text-darktext-primary hover:border-dark-border'
            }`}
          >
            <History className="w-4 h-4" />
            <span>Instantáneas de Contexto</span>
            <span
              className={`px-1.5 py-0.5 text-[10px] rounded-full font-bold ${
                activeTab === 'context'
                  ? 'bg-emerald-950/80 text-brand-emerald border border-emerald-700/40'
                  : 'bg-dark-elevated text-darktext-secondary border border-dark-border'
              }`}
            >
              {snapshots.length}
            </span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('decisions')}
            className={`inline-flex items-center space-x-2 py-3 px-1 border-b-2 font-medium text-xs transition-colors ${
              activeTab === 'decisions'
                ? 'border-brand-emerald text-brand-emerald font-semibold'
                : 'border-transparent text-darktext-secondary hover:text-darktext-primary hover:border-dark-border'
            }`}
          >
            <Scale className="w-4 h-4" />
            <span>Decisiones de Negocio</span>
            <span
              className={`px-1.5 py-0.5 text-[10px] rounded-full font-bold ${
                activeTab === 'decisions'
                  ? 'bg-emerald-950/80 text-brand-emerald border border-emerald-700/40'
                  : 'bg-dark-elevated text-darktext-secondary border border-dark-border'
              }`}
            >
              {decisions.length}
            </span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('alternatives')}
            className={`inline-flex items-center space-x-2 py-3 px-1 border-b-2 font-medium text-xs transition-colors ${
              activeTab === 'alternatives'
                ? 'border-brand-emerald text-brand-emerald font-semibold'
                : 'border-transparent text-darktext-secondary hover:text-darktext-primary hover:border-dark-border'
            }`}
          >
            <Layers className="w-4 h-4" />
            <span>Matriz de Alternativas</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('audit')}
            className={`inline-flex items-center space-x-2 py-3 px-1 border-b-2 font-medium text-xs transition-colors ${
              activeTab === 'audit'
                ? 'border-brand-emerald text-brand-emerald font-semibold'
                : 'border-transparent text-darktext-secondary hover:text-darktext-primary hover:border-dark-border'
            }`}
          >
            <ShieldCheck className="w-4 h-4" />
            <span>Pista de Auditoría</span>
            <span
              className={`px-1.5 py-0.5 text-[10px] rounded-full font-bold ${
                activeTab === 'audit'
                  ? 'bg-emerald-950/80 text-brand-emerald border border-emerald-700/40'
                  : 'bg-dark-elevated text-darktext-secondary border border-dark-border'
              }`}
            >
              {auditEvents.length}
            </span>
          </button>
        </nav>
      </div>

      {/* Contenido de la Pestaña: Ficha General */}
      {activeTab === 'general' && (
        <div className="space-y-6 animate-in fade-in duration-150">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Columna Izquierda: Definición del Problema */}
            <div className="space-y-6">
              {/* Descripción de la Empresa */}
              <div className="bg-dark-card border border-dark-border rounded-xl p-5 shadow-sm space-y-2">
                <h3 className="font-semibold text-darktext-primary text-xs flex items-center space-x-2">
                  <Building2 className="w-4 h-4 text-brand-emerald" />
                  <span>Descripción de la Empresa</span>
                </h3>
                <p className="text-xs text-darktext-primary leading-relaxed whitespace-pre-line bg-dark-elevated p-3.5 rounded-lg border border-dark-border">
                  {project.company_description}
                </p>
              </div>

              {/* Necesidad de Negocio */}
              <div className="bg-dark-card border border-dark-border rounded-xl p-5 shadow-sm space-y-2">
                <h3 className="font-semibold text-darktext-primary text-xs flex items-center space-x-2">
                  <Target className="w-4 h-4 text-brand-turquoise" />
                  <span>Necesidad o Problema de Negocio</span>
                </h3>
                <p className="text-xs text-darktext-primary leading-relaxed whitespace-pre-line bg-dark-elevated p-3.5 rounded-lg border border-dark-border">
                  {project.business_need}
                </p>
              </div>

              {/* Objetivo Esperado */}
              <div className="bg-dark-card border border-dark-border rounded-xl p-5 shadow-sm space-y-2">
                <h3 className="font-semibold text-darktext-primary text-xs flex items-center space-x-2">
                  <Sparkles className="w-4 h-4 text-brand-warning" />
                  <span>Objetivo Analítico Esperado</span>
                </h3>
                <p className="text-xs text-darktext-primary leading-relaxed whitespace-pre-line bg-dark-elevated p-3.5 rounded-lg border border-dark-border">
                  {project.expected_objective}
                </p>
              </div>
            </div>

            {/* Columna Derecha: Criterios, Reglas y Restricciones */}
            <div className="space-y-6">
              {/* Criterios de Éxito */}
              <div className="bg-dark-card border border-dark-border rounded-xl p-5 shadow-sm space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-darktext-primary text-xs flex items-center space-x-2">
                    <Check className="w-4 h-4 text-brand-emerald" />
                    <span>Criterios de Éxito Verificables</span>
                  </h3>
                  <span className="text-[11px] font-semibold text-brand-emerald bg-dark-elevated border border-dark-border px-2 py-0.5 rounded">
                    {project.success_criteria.length} definidos
                  </span>
                </div>

                <ul className="space-y-2 text-xs">
                  {project.success_criteria.map((criterion, index) => (
                    <li
                      key={index}
                      className="flex items-start space-x-2 bg-dark-elevated border border-dark-border p-2.5 rounded-lg text-darktext-primary"
                    >
                      <span className="w-4 h-4 rounded-full bg-emerald-950/80 border border-emerald-600/40 text-brand-emerald font-mono text-[10px] flex items-center justify-center flex-shrink-0 mt-0.5 font-bold">
                        {index + 1}
                      </span>
                      <span className="leading-relaxed">{criterion}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Reglas de Negocio */}
              <div className="bg-dark-card border border-dark-border rounded-xl p-5 shadow-sm space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-darktext-primary text-xs flex items-center space-x-2">
                    <Shield className="w-4 h-4 text-brand-turquoise" />
                    <span>Reglas de Negocio</span>
                  </h3>
                  <span className="text-[11px] text-darktext-secondary font-medium">
                    {project.business_rules.length} declaradas
                  </span>
                </div>

                {project.business_rules.length === 0 ? (
                  <p className="text-xs text-darktext-secondary italic">No se declararon reglas de negocio adicionales.</p>
                ) : (
                  <ul className="space-y-1.5 text-xs">
                    {project.business_rules.map((rule, index) => (
                      <li
                        key={index}
                        className="flex items-start space-x-2 bg-dark-elevated border border-dark-border p-2 rounded-lg text-darktext-secondary"
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-brand-turquoise mt-1.5 flex-shrink-0"></span>
                        <span className="text-darktext-primary">{rule}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Restricciones */}
              <div className="bg-dark-card border border-dark-border rounded-xl p-5 shadow-sm space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-darktext-primary text-xs flex items-center space-x-2">
                    <FileText className="w-4 h-4 text-darktext-secondary" />
                    <span>Restricciones del Proyecto</span>
                  </h3>
                  <span className="text-[11px] text-darktext-secondary font-medium">
                    {project.constraints.length} declaradas
                  </span>
                </div>

                {project.constraints.length === 0 ? (
                  <p className="text-xs text-darktext-secondary italic">No se declararon restricciones adicionales.</p>
                ) : (
                  <ul className="space-y-1.5 text-xs">
                    {project.constraints.map((constraint, index) => (
                      <li
                        key={index}
                        className="flex items-start space-x-2 bg-dark-elevated border border-dark-border p-2 rounded-lg text-darktext-secondary"
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-brand-warning mt-1.5 flex-shrink-0"></span>
                        <span className="text-darktext-primary">{constraint}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>

          {/* Próximos Pasos en el Ciclo de Vida */}
          <div className="bg-dark-secondary border border-dark-border rounded-xl p-5 shadow-sm space-y-3 text-xs">
            <div className="flex items-center space-x-2 text-darktext-primary font-bold">
              <Layers className="w-4 h-4 text-brand-emerald" />
              <span>Siguiente Etapa del Ciclo Metodológico</span>
            </div>
            <p className="text-darktext-secondary leading-relaxed">
              Este proyecto cuenta con su registro de entendimiento de negocio gobernado. Puedes gestionar
              versiones inmutables de su contexto, formalizar decisiones analíticas y auditar la cadena de custodia mediante las pestañas superiores.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
              <div className="p-3 bg-dark-card rounded-lg border border-dark-border">
                <span className="font-semibold text-brand-emerald block mb-1">M11.3C: Auditoría y Matriz de Alternativas</span>
                <span className="text-[11px] text-darktext-secondary">
                  Trazabilidad criptográfica de eventos y comparación de enfoques de modelado para cierre de M1.
                </span>
              </div>
              <div className="p-3 bg-dark-card rounded-lg border border-dark-border">
                <span className="font-semibold text-brand-turquoise block mb-1">M11.4: Ingesta Bronze y Datos</span>
                <span className="text-[11px] text-darktext-secondary">
                  Carga del dataset CSV crudo y perfilado exploratorio automatizado.
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Contenido de la Pestaña: Instantáneas de Contexto */}
      {activeTab === 'context' && (
        <div className="animate-in fade-in duration-150">
          <ContextTimeline
            project={project}
            snapshots={snapshots}
            isLoading={isLoadingSnapshots}
            error={snapshotsError}
            onRetry={fetchSnapshots}
            onSnapshotCreated={handleSnapshotCreated}
            isReadOnly={project.status === 'archived'}
          />
        </div>
      )}

      {/* Contenido de la Pestaña: Decisiones de Negocio */}
      {activeTab === 'decisions' && (
        <div className="animate-in fade-in duration-150">
          <DecisionList
            projectId={project.id}
            decisions={decisions}
            isLoading={isLoadingDecisions}
            error={decisionsError}
            onRetry={fetchDecisions}
            onDecisionCreated={handleDecisionCreated}
            defaultDecidedBy={project.owner_id || ''}
            isReadOnly={project.status === 'archived'}
          />
        </div>
      )}

      {/* Contenido de la Pestaña: Matriz de Alternativas */}
      {activeTab === 'alternatives' && (
        <div className="animate-in fade-in duration-150">
          <AlternativesMatrix
            decisions={decisions}
            onOpenDecisionModal={() => setActiveTab('decisions')}
          />
        </div>
      )}

      {/* Contenido de la Pestaña: Pista de Auditoría */}
      {activeTab === 'audit' && (
        <div className="animate-in fade-in duration-150">
          <AuditTrailView
            projectId={project.id}
            events={auditEvents}
            isLoading={isLoadingAudit}
            error={auditError}
            onRetry={fetchAuditEvents}
          />
        </div>
      )}

      <ProjectLifecycleModal
        isOpen={lifecycleAction !== null}
        action={lifecycleAction ?? 'archive'}
        project={project}
        isSubmitting={isLifecycleSubmitting}
        errorMessage={lifecycleError}
        onClose={() => {
          if (!isLifecycleSubmitting) {
            setLifecycleAction(null);
            setLifecycleError(null);
          }
        }}
        onSubmit={handleLifecycleSubmit}
      />
    </div>
  );
};
