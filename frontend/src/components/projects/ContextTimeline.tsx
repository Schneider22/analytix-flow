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
}

export const ContextTimeline: React.FC<ContextTimelineProps> = ({
  project,
  snapshots,
  isLoading,
  error,
  onRetry,
  onSnapshotCreated,
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
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center space-x-2">
            <h3 className="text-base font-bold text-slate-900">
              Línea de Tiempo del Contexto de Negocio
            </h3>
            <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-slate-100 text-slate-700 border border-slate-200">
              {snapshots.length} {snapshots.length === 1 ? 'versión' : 'versiones'}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Historial inmutable y criptográficamente sellado de suposiciones, restricciones y criterios de éxito.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setIsModalOpen(true)}
          className="inline-flex items-center justify-center space-x-1.5 px-3.5 py-2 text-xs font-semibold rounded-lg text-white bg-emerald-600 hover:bg-emerald-700 transition-colors shadow-sm self-start sm:self-auto"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Registrar Nueva Versión</span>
        </button>
      </div>

      {/* Estados de Carga y Error */}
      {isLoading && (
        <div className="p-8 text-center bg-white rounded-xl border border-slate-200 shadow-sm">
          <RefreshCw className="w-6 h-6 animate-spin text-emerald-600 mx-auto mb-2" />
          <p className="text-xs text-slate-600">Cargando historial de versiones de contexto...</p>
        </div>
      )}

      {error && !isLoading && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 flex items-start space-x-3">
          <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="text-xs font-bold">Error al cargar las instantáneas de contexto</h4>
            <p className="text-xs mt-0.5">{error}</p>
            <button
              type="button"
              onClick={onRetry}
              className="mt-2 text-xs font-semibold text-rose-700 hover:text-rose-900 underline inline-flex items-center space-x-1"
            >
              <RefreshCw className="w-3 h-3" />
              <span>Reintentar carga</span>
            </button>
          </div>
        </div>
      )}

      {/* Estado Vacío */}
      {!isLoading && !error && sortedSnapshots.length === 0 && (
        <div className="p-8 text-center bg-white rounded-xl border border-dashed border-slate-300">
          <History className="w-10 h-10 text-slate-300 mx-auto mb-2" />
          <h4 className="text-sm font-semibold text-slate-800">
            Sin instantáneas registradas en el historial
          </h4>
          <p className="text-xs text-slate-500 max-w-md mx-auto mt-1 mb-4">
            Este proyecto actualmente opera con la definición base registrada en su creación.
            Puedes formalizar la versión inicial (v1) para habilitar auditoría y control de versiones.
          </p>
          <button
            type="button"
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center space-x-1.5 px-3.5 py-2 text-xs font-semibold rounded-lg text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Crear Versión Inicial (v1)</span>
          </button>
        </div>
      )}

      {/* Lista / Timeline de Versiones */}
      {!isLoading && !error && sortedSnapshots.length > 0 && (
        <div className="relative pl-6 space-y-6 before:content-[''] before:absolute before:left-2.5 before:top-3 before:bottom-3 before:w-0.5 before:bg-slate-200">
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
                      ? 'bg-emerald-600 border-white ring-4 ring-emerald-100 text-white'
                      : 'bg-white border-slate-300 text-slate-400'
                  }`}
                >
                  <GitCommit className="w-3 h-3" />
                </div>

                {/* Tarjeta de la Versión */}
                <div
                  className={`bg-white rounded-xl border transition-all ${
                    isLatest
                      ? 'border-emerald-300 shadow-sm ring-1 ring-emerald-100'
                      : 'border-slate-200 hover:border-slate-300 shadow-xs'
                  }`}
                >
                  {/* Cabecera de la Tarjeta */}
                  <div className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100">
                    <div className="space-y-1">
                      <div className="flex items-center space-x-2">
                        <span className="text-sm font-bold text-slate-900">
                          Versión {snapshot.version}
                        </span>
                        {isLatest ? (
                          <span className="inline-flex items-center space-x-1 px-2 py-0.5 text-[11px] font-semibold rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>Versión Activa</span>
                          </span>
                        ) : (
                          <span className="text-[11px] font-medium text-slate-400">
                            (Histórico)
                          </span>
                        )}
                        {snapshot.predecessor_id ? (
                          <span className="text-[11px] text-slate-500 font-mono">
                            Predecesor: {snapshot.predecessor_id.slice(0, 8)}...
                          </span>
                        ) : (
                          <span className="text-[11px] text-slate-400 italic">
                            (Versión Raíz)
                          </span>
                        )}
                      </div>

                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
                        <span className="inline-flex items-center space-x-1">
                          <User className="w-3.5 h-3.5 text-slate-400" />
                          <span className="font-medium text-slate-700">{snapshot.created_by}</span>
                        </span>
                        <span className="inline-flex items-center space-x-1">
                          <Calendar className="w-3.5 h-3.5 text-slate-400" />
                          <span>{formatDate(snapshot.created_at)}</span>
                        </span>
                      </div>
                    </div>

                    {/* Hash y Botón Copiar */}
                    <div className="flex items-center space-x-2 self-start sm:self-auto">
                      <div className="inline-flex items-center space-x-1.5 px-2.5 py-1 bg-slate-50 border border-slate-200 rounded-lg text-slate-600 text-xs font-mono">
                        <Hash className="w-3 h-3 text-slate-400" />
                        <span title={snapshot.content_hash}>
                          {snapshot.content_hash.slice(0, 8)}...{snapshot.content_hash.slice(-6)}
                        </span>
                        <button
                          type="button"
                          onClick={() => handleCopyHash(snapshot.content_hash, snapshot.id)}
                          className="text-slate-400 hover:text-slate-700 p-0.5 transition-colors"
                          title="Copiar Content Hash completo"
                          aria-label={`Copiar hash de la versión ${snapshot.version}`}
                        >
                          {copiedHashId === snapshot.id ? (
                            <Check className="w-3.5 h-3.5 text-emerald-600" />
                          ) : (
                            <Copy className="w-3.5 h-3.5" />
                          )}
                        </button>
                      </div>

                      <button
                        type="button"
                        onClick={() => toggleExpand(snapshot.id)}
                        className="inline-flex items-center space-x-1 px-2.5 py-1 text-xs font-semibold text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors"
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
                  <div className="px-4 py-3 sm:px-5 bg-slate-50/50 text-xs text-slate-600 flex flex-wrap gap-4 border-b border-slate-100">
                    <div>
                      <span className="font-semibold text-slate-700">Empresa:</span>{' '}
                      {ctx.company_name}
                    </div>
                    <div>
                      <span className="font-semibold text-slate-700">Criterios:</span>{' '}
                      {ctx.success_criteria?.length ?? 0}
                    </div>
                    <div>
                      <span className="font-semibold text-slate-700">Suposiciones:</span>{' '}
                      {ctx.assumptions?.length ?? 0}
                    </div>
                    <div>
                      <span className="font-semibold text-slate-700">Reglas:</span>{' '}
                      {ctx.business_rules?.length ?? 0}
                    </div>
                  </div>

                  {/* Detalle Desplegable */}
                  {isExpanded && (
                    <div className="p-4 sm:p-5 space-y-4 text-xs animate-in fade-in duration-150">
                      {/* Necesidad y Objetivo */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                          <h5 className="font-bold text-slate-800 mb-1">Necesidad de Negocio</h5>
                          <p className="text-slate-600 whitespace-pre-wrap">{ctx.business_need}</p>
                        </div>
                        <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                          <h5 className="font-bold text-slate-800 mb-1">Objetivo Esperado</h5>
                          <p className="text-slate-600 whitespace-pre-wrap">{ctx.expected_objective}</p>
                        </div>
                      </div>

                      {/* Descripción de la Empresa */}
                      <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                        <h5 className="font-bold text-slate-800 mb-1">Descripción de la Empresa</h5>
                        <p className="text-slate-600 whitespace-pre-wrap">{ctx.company_description}</p>
                      </div>

                      {/* Suposiciones (Assumptions) */}
                      <div>
                        <h5 className="font-bold text-slate-800 mb-1.5 flex items-center space-x-1.5">
                          <span>Suposiciones e Hipótesis Técnicas ({ctx.assumptions?.length ?? 0})</span>
                        </h5>
                        {ctx.assumptions && ctx.assumptions.length > 0 ? (
                          <ul className="list-disc list-inside space-y-1 bg-amber-50/50 p-3 rounded-lg border border-amber-200 text-amber-950">
                            {ctx.assumptions.map((assump, idx) => (
                              <li key={idx}>{assump}</li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-slate-400 italic">No se registraron suposiciones explícitas.</p>
                        )}
                      </div>

                      {/* Criterios de Éxito */}
                      <div>
                        <h5 className="font-bold text-slate-800 mb-1.5">
                          Criterios de Éxito Medibles ({ctx.success_criteria?.length ?? 0})
                        </h5>
                        {ctx.success_criteria && ctx.success_criteria.length > 0 ? (
                          <ul className="list-disc list-inside space-y-1 bg-emerald-50/50 p-3 rounded-lg border border-emerald-200 text-emerald-950">
                            {ctx.success_criteria.map((crit, idx) => (
                              <li key={idx}>{crit}</li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-slate-400 italic">No se registraron criterios de éxito.</p>
                        )}
                      </div>

                      {/* Reglas de Negocio */}
                      <div>
                        <h5 className="font-bold text-slate-800 mb-1.5">
                          Reglas de Negocio ({ctx.business_rules?.length ?? 0})
                        </h5>
                        {ctx.business_rules && ctx.business_rules.length > 0 ? (
                          <ul className="list-disc list-inside space-y-1 bg-blue-50/50 p-3 rounded-lg border border-blue-200 text-blue-950">
                            {ctx.business_rules.map((rule, idx) => (
                              <li key={idx}>{rule}</li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-slate-400 italic">No se registraron reglas de negocio.</p>
                        )}
                      </div>

                      {/* Restricciones */}
                      <div>
                        <h5 className="font-bold text-slate-800 mb-1.5">
                          Restricciones Técnicas ({ctx.constraints?.length ?? 0})
                        </h5>
                        {ctx.constraints && ctx.constraints.length > 0 ? (
                          <ul className="list-disc list-inside space-y-1 bg-rose-50/50 p-3 rounded-lg border border-rose-200 text-rose-950">
                            {ctx.constraints.map((cons, idx) => (
                              <li key={idx}>{cons}</li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-slate-400 italic">No se registraron restricciones.</p>
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
