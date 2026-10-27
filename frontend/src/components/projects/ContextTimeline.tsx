import React, { useState } from 'react';
import { ContextRead, ProjectRead } from '../../types/projects';
import { ContextCreateModal } from './ContextCreateModal';
import {
  History,
  Plus,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  RefreshCw,
  GitCommit,
  CheckCircle2,
  Calendar,
  User,
  Hash,
} from 'lucide-react';

interface ContextTimelineProps {
  project: ProjectRead;
  snapshots: ContextRead[];
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
  onSnapshotCreated: (snapshot: ContextRead) => void;
  isReadOnly?: boolean;
}

export const ContextTimeline: React.FC<ContextTimelineProps> = ({
  project,
  snapshots,
  isLoading,
  error,
  onRetry,
  onSnapshotCreated,
  isReadOnly = false,
}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [expandedIds, setExpandedIds] = useState<Record<string, boolean>>({});
  const [copiedHashId, setCopiedHashId] = useState<string | null>(null);

  // Snapshots sorted ascending by version
  const sortedSnapshots = [...snapshots].sort((a, b) => a.version - b.version);
  const latestSnapshot = sortedSnapshots.length > 0 ? sortedSnapshots[sortedSnapshots.length - 1] : null;

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const handleCopyHash = async (hash: string, id: string) => {
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(hash);
        setCopiedHashId(id);
        setTimeout(() => setCopiedHashId(null), 2000);
      }
    } catch {
      // Fallback or ignore in non-secure context
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleString('es-ES', {
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="space-y-6">
      {/* Cabecera de la sección */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-dark-border">
        <div>
          <div className="flex items-center space-x-2">
            <h3 className="text-base font-bold text-darktext-primary">
              Línea de Tiempo del Contexto de Negocio
            </h3>
            <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-dark-elevated text-brand-emerald border border-dark-border">
              {snapshots.length} {snapshots.length === 1 ? 'versión' : 'versiones'}
            </span>
          </div>
          <p className="text-xs text-darktext-secondary mt-1">
            Historial inmutable y criptográficamente sellado de suposiciones, restricciones y criterios de éxito.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setIsModalOpen(true)}
          disabled={isReadOnly}
          className="inline-flex items-center justify-center space-x-1.5 px-3.5 py-2 text-xs font-bold rounded-lg text-dark-primary bg-brand-emerald hover:bg-brand-emeraldHover transition-colors shadow-sm shadow-emerald-950/40 self-start sm:self-auto"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Registrar Nueva Versión</span>
        </button>
      </div>

      {/* Estados de Carga y Error */}
      {isLoading && (
        <div className="p-8 text-center bg-dark-card rounded-xl border border-dark-border shadow-sm">
          <RefreshCw className="w-6 h-6 animate-spin text-brand-emerald mx-auto mb-2" />
          <p className="text-xs text-darktext-secondary">Cargando historial de versiones de contexto...</p>
        </div>
      )}

      {error && !isLoading && (
        <div className="p-4 bg-rose-950/30 border border-brand-error/40 rounded-xl text-darktext-primary flex items-start space-x-3">
          <AlertTriangle className="w-5 h-5 text-brand-error flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="text-xs font-bold text-brand-error">Error al cargar las instantáneas de contexto</h4>
            <p className="text-xs mt-0.5 text-rose-300">{error}</p>
            <button
              type="button"
              onClick={onRetry}
              className="mt-2 text-xs font-semibold text-brand-error hover:text-rose-300 underline inline-flex items-center space-x-1"
            >
              <RefreshCw className="w-3 h-3" />
              <span>Reintentar carga</span>
            </button>
          </div>
        </div>
      )}

      {/* Estado Vacío */}
      {!isLoading && !error && sortedSnapshots.length === 0 && (
        <div className="p-8 text-center bg-dark-card rounded-xl border border-dashed border-dark-border">
          <History className="w-10 h-10 text-darktext-secondary mx-auto mb-2" />
          <h4 className="text-sm font-semibold text-darktext-primary">
            Sin instantáneas registradas en el historial
          </h4>
          <p className="text-xs text-darktext-secondary max-w-md mx-auto mt-1 mb-4">
            Este proyecto actualmente opera con la definición base registrada en su creación.
            Puedes formalizar la versión inicial (v1) para habilitar auditoría y control de versiones.
          </p>
          {isReadOnly ? (
            <p className="text-xs text-brand-warning">Proyecto archivado: consulta histórica en modo solo lectura.</p>
          ) : (
            <button
              type="button"
              onClick={() => setIsModalOpen(true)}
              className="inline-flex items-center space-x-1.5 px-3.5 py-2 text-xs font-semibold rounded-lg text-brand-emerald bg-dark-elevated hover:bg-dark-border border border-dark-border transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Crear Versión Inicial (v1)</span>
            </button>
          )}
        </div>
      )}

      {/* Lista / Timeline de Versiones */}
      {!isLoading && !error && sortedSnapshots.length > 0 && (
        <div className="relative pl-6 space-y-6 before:content-[''] before:absolute before:left-2.5 before:top-3 before:bottom-3 before:w-0.5 before:bg-dark-border">
          {sortedSnapshots.map((snapshot) => {
            const isLatest = latestSnapshot?.id === snapshot.id;
            const isExpanded = !!expandedIds[snapshot.id];
            const ctx = snapshot.context;

            return (
              <div key={snapshot.id} className="relative group">
                {/* Nodo en la línea vertical */}
                <div
                  className={`absolute -left-6 top-3 w-5 h-5 rounded-full flex items-center justify-center border-2 transition-colors ${
                    isLatest
                      ? 'bg-brand-emerald border-dark-card ring-4 ring-emerald-950/60 text-dark-primary font-bold'
                      : 'bg-dark-card border-dark-border text-darktext-secondary'
                  }`}
                >
                  <GitCommit className="w-3 h-3" />
                </div>

                {/* Tarjeta de la Versión */}
                <div
                  className={`bg-dark-card rounded-xl border transition-all ${
                    isLatest
                      ? 'border-brand-emerald/50 shadow-md ring-1 ring-emerald-950/40'
                      : 'border-dark-border hover:border-dark-border/80 shadow-sm'
                  }`}
                >
                  {/* Cabecera de la Tarjeta */}
                  <div className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-dark-border/80">
                    <div className="space-y-1">
                      <div className="flex items-center space-x-2">
                        <span className="text-sm font-bold text-darktext-primary">
                          Versión {snapshot.version}
                        </span>
                        {isLatest ? (
                          <span className="inline-flex items-center space-x-1 px-2 py-0.5 text-[11px] font-semibold rounded-full bg-emerald-950/80 text-brand-emerald border border-emerald-700/50">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>Versión Activa</span>
                          </span>
                        ) : (
                          <span className="text-[11px] font-medium text-darktext-secondary">
                            (Histórico)
                          </span>
                        )}
                        {snapshot.predecessor_id ? (
                          <span className="text-[11px] text-brand-turquoise font-mono">
                            Predecesor: {snapshot.predecessor_id.slice(0, 8)}...
                          </span>
                        ) : (
                          <span className="text-[11px] text-darktext-secondary/70 italic">
                            (Versión Raíz)
                          </span>
                        )}
                      </div>

                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-darktext-secondary">
                        <span className="inline-flex items-center space-x-1">
                          <User className="w-3.5 h-3.5 text-darktext-secondary" />
                          <span className="font-medium text-darktext-primary">{snapshot.created_by}</span>
                        </span>
                        <span className="inline-flex items-center space-x-1">
                          <Calendar className="w-3.5 h-3.5 text-darktext-secondary" />
                          <span>{formatDate(snapshot.created_at)}</span>
                        </span>
                      </div>
                    </div>

                    {/* Hash y Botón Copiar */}
                    <div className="flex items-center space-x-2 self-start sm:self-auto">
                      <div className="inline-flex items-center space-x-1.5 px-2.5 py-1 bg-dark-elevated border border-dark-border rounded-lg text-brand-turquoise text-xs font-mono">
                        <Hash className="w-3 h-3 text-darktext-secondary" />
                        <span title={snapshot.content_hash}>
                          {snapshot.content_hash.slice(0, 8)}...{snapshot.content_hash.slice(-6)}
                        </span>
                        <button
                          type="button"
                          onClick={() => handleCopyHash(snapshot.content_hash, snapshot.id)}
                          className="text-darktext-secondary hover:text-brand-emerald p-0.5 transition-colors"
                          title="Copiar Content Hash completo"
                          aria-label={`Copiar hash de la versión ${snapshot.version}`}
                        >
                          {copiedHashId === snapshot.id ? (
                            <Check className="w-3.5 h-3.5 text-brand-emerald" />
                          ) : (
                            <Copy className="w-3.5 h-3.5" />
                          )}
                        </button>
                      </div>

                      <button
                        type="button"
                        onClick={() => toggleExpand(snapshot.id)}
                        className="inline-flex items-center space-x-1 px-2.5 py-1 text-xs font-semibold text-darktext-primary hover:text-white bg-dark-elevated hover:bg-dark-border border border-dark-border rounded-lg transition-colors"
                        aria-expanded={isExpanded}
                      >
                        <span>{isExpanded ? 'Ocultar' : 'Detalles'}</span>
                        {isExpanded ? (
                          <ChevronUp className="w-3.5 h-3.5" />
                        ) : (
                          <ChevronDown className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Resumen siempre visible */}
                  <div className="px-4 py-3 sm:px-5 bg-dark-elevated/40 text-xs text-darktext-secondary flex flex-wrap gap-4 border-b border-dark-border/60">
                    <div>
                      <span className="font-semibold text-darktext-primary">Empresa:</span>{' '}
                      {ctx.company_name}
                    </div>
                    <div>
                      <span className="font-semibold text-darktext-primary">Criterios:</span>{' '}
                      {ctx.success_criteria?.length ?? 0}
                    </div>
                    <div>
                      <span className="font-semibold text-darktext-primary">Suposiciones:</span>{' '}
                      {ctx.assumptions?.length ?? 0}
                    </div>
                    <div>
                      <span className="font-semibold text-darktext-primary">Reglas:</span>{' '}
                      {ctx.business_rules?.length ?? 0}
                    </div>
                  </div>

                  {/* Detalle Desplegable */}
                  {isExpanded && (
                    <div className="p-4 sm:p-5 space-y-4 text-xs animate-in fade-in duration-150">
                      {/* Necesidad y Objetivo */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="p-3 bg-dark-elevated rounded-lg border border-dark-border">
                          <h5 className="font-bold text-darktext-primary mb-1">Necesidad de Negocio</h5>
                          <p className="text-darktext-secondary whitespace-pre-wrap">{ctx.business_need}</p>
                        </div>
                        <div className="p-3 bg-dark-elevated rounded-lg border border-dark-border">
                          <h5 className="font-bold text-darktext-primary mb-1">Objetivo Esperado</h5>
                          <p className="text-darktext-secondary whitespace-pre-wrap">{ctx.expected_objective}</p>
                        </div>
                      </div>

                      {/* Descripción de la Empresa */}
                      <div className="p-3 bg-dark-elevated rounded-lg border border-dark-border">
                        <h5 className="font-bold text-darktext-primary mb-1">Descripción de la Empresa</h5>
                        <p className="text-darktext-secondary whitespace-pre-wrap">{ctx.company_description}</p>
                      </div>

                      {/* Suposiciones (Assumptions) */}
                      <div>
                        <h5 className="font-bold text-darktext-primary mb-1.5 flex items-center space-x-1.5">
                          <span>Suposiciones e Hipótesis Técnicas ({ctx.assumptions?.length ?? 0})</span>
                        </h5>
                        {ctx.assumptions && ctx.assumptions.length > 0 ? (
                          <ul className="list-disc list-inside space-y-1 bg-amber-950/30 p-3 rounded-lg border border-amber-800/40 text-amber-200">
                            {ctx.assumptions.map((assump, idx) => (
                              <li key={idx}>{assump}</li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-darktext-secondary italic">No se registraron suposiciones explícitas.</p>
                        )}
                      </div>

                      {/* Criterios de Éxito */}
                      <div>
                        <h5 className="font-bold text-darktext-primary mb-1.5">
                          Criterios de Éxito Medibles ({ctx.success_criteria?.length ?? 0})
                        </h5>
                        {ctx.success_criteria && ctx.success_criteria.length > 0 ? (
                          <ul className="list-disc list-inside space-y-1 bg-emerald-950/30 p-3 rounded-lg border border-emerald-800/40 text-emerald-200">
                            {ctx.success_criteria.map((crit, idx) => (
                              <li key={idx}>{crit}</li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-darktext-secondary italic">No se registraron criterios de éxito.</p>
                        )}
                      </div>

                      {/* Reglas de Negocio */}
                      <div>
                        <h5 className="font-bold text-darktext-primary mb-1.5">
                          Reglas de Negocio ({ctx.business_rules?.length ?? 0})
                        </h5>
                        {ctx.business_rules && ctx.business_rules.length > 0 ? (
                          <ul className="list-disc list-inside space-y-1 bg-cyan-950/30 p-3 rounded-lg border border-cyan-800/40 text-cyan-200">
                            {ctx.business_rules.map((rule, idx) => (
                              <li key={idx}>{rule}</li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-darktext-secondary italic">No se registraron reglas de negocio.</p>
                        )}
                      </div>

                      {/* Restricciones */}
                      <div>
                        <h5 className="font-bold text-darktext-primary mb-1.5">
                          Restricciones Técnicas ({ctx.constraints?.length ?? 0})
                        </h5>
                        {ctx.constraints && ctx.constraints.length > 0 ? (
                          <ul className="list-disc list-inside space-y-1 bg-rose-950/30 p-3 rounded-lg border border-rose-800/40 text-rose-200">
                            {ctx.constraints.map((cons, idx) => (
                              <li key={idx}>{cons}</li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-darktext-secondary italic">No se registraron restricciones.</p>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Modal para Registrar Nueva Versión */}
      <ContextCreateModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        project={project}
        latestSnapshot={latestSnapshot}
        onSnapshotCreated={(newSnapshot) => {
          onSnapshotCreated(newSnapshot);
          setIsModalOpen(false);
        }}
      />
    </div>
  );
};
