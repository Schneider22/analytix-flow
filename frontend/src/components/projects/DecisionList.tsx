import React, { useState } from 'react';
import { DecisionRead } from '../../types/projects';
import { DecisionCreateModal } from './DecisionCreateModal';
import {
  Scale,
  Plus,
  CheckCircle2,
  Clock,
  XCircle,
  AlertTriangle,
  RefreshCw,
  User,
  Calendar,
  Check,
} from 'lucide-react';

interface DecisionListProps {
  projectId: string;
  decisions: DecisionRead[];
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
  onDecisionCreated: (decision: DecisionRead) => void;
  defaultDecidedBy?: string;
  isReadOnly?: boolean;
}

export const DecisionList: React.FC<DecisionListProps> = ({
  projectId,
  decisions,
  isLoading,
  error,
  onRetry,
  onDecisionCreated,
  defaultDecidedBy,
  isReadOnly = false,
}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);

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

  const renderStatusBadge = (status: DecisionRead['status']) => {
    switch (status) {
      case 'decided':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-950/80 text-brand-emerald border border-emerald-700/50">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Decidida</span>
          </span>
        );
      case 'pending':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 text-xs font-semibold rounded-full bg-amber-950/80 text-brand-warning border border-amber-700/50">
            <Clock className="w-3.5 h-3.5" />
            <span>Pendiente</span>
          </span>
        );
      case 'rejected':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 text-xs font-semibold rounded-full bg-rose-950/80 text-brand-error border border-rose-800/50">
            <XCircle className="w-3.5 h-3.5" />
            <span>Rechazada</span>
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-0.5 text-xs font-medium rounded-full bg-dark-elevated text-darktext-secondary border border-dark-border">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Cabecera de la sección */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-dark-border">
        <div>
          <div className="flex items-center space-x-2">
            <h3 className="text-base font-bold text-darktext-primary">Decisiones de Negocio</h3>
            <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-dark-elevated text-brand-emerald border border-dark-border">
              {decisions.length} {decisions.length === 1 ? 'decisión' : 'decisiones'}
            </span>
          </div>
          <p className="text-xs text-darktext-secondary mt-1">
            Registro auditable de alternativas evaluadas, justificaciones y opciones analíticas adoptadas.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setIsModalOpen(true)}
          disabled={isReadOnly}
          className="inline-flex items-center justify-center space-x-1.5 px-3.5 py-2 text-xs font-bold rounded-lg text-dark-primary bg-brand-emerald hover:bg-brand-emeraldHover transition-colors shadow-sm shadow-emerald-950/40 self-start sm:self-auto"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Registrar Decisión</span>
        </button>
      </div>

      {/* Estados de Carga y Error */}
      {isLoading && (
        <div className="p-8 text-center bg-dark-card rounded-xl border border-dark-border shadow-sm">
          <RefreshCw className="w-6 h-6 animate-spin text-brand-emerald mx-auto mb-2" />
          <p className="text-xs text-darktext-secondary">Cargando decisiones de negocio...</p>
        </div>
      )}

      {error && !isLoading && (
        <div className="p-4 bg-rose-950/30 border border-brand-error/40 rounded-xl text-darktext-primary flex items-start space-x-3">
          <AlertTriangle className="w-5 h-5 text-brand-error flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="text-xs font-bold text-brand-error">Error al cargar las decisiones de negocio</h4>
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
      {!isLoading && !error && decisions.length === 0 && (
        <div className="p-8 text-center bg-dark-card rounded-xl border border-dashed border-dark-border">
          <Scale className="w-10 h-10 text-darktext-secondary mx-auto mb-2" />
          <h4 className="text-sm font-semibold text-darktext-primary">
            Sin decisiones de negocio registradas
          </h4>
          <p className="text-xs text-darktext-secondary max-w-md mx-auto mt-1 mb-4">
            No se han formalizado decisiones ni selección de alternativas para este proyecto.
            Puedes registrar una nueva decisión o usar la plantilla estándar M1.
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
              <span>Registrar Primera Decisión</span>
            </button>
          )}
        </div>
      )}

      {/* Listado de Decisiones */}
      {!isLoading && !error && decisions.length > 0 && (
        <div className="space-y-4">
          {decisions.map((decision) => (
            <div
              key={decision.id}
              className="bg-dark-card rounded-xl border border-dark-border hover:border-dark-border/80 shadow-sm p-5 space-y-4 transition-all"
            >
              {/* Cabecera de la Decisión */}
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    {renderStatusBadge(decision.status)}
                    <span className="px-2 py-0.5 text-[11px] font-mono font-medium rounded-md bg-dark-elevated text-brand-turquoise border border-dark-border">
                      {decision.decision_type}
                    </span>
                  </div>
                  <h4 className="text-sm font-bold text-darktext-primary pt-1">{decision.question}</h4>
                </div>

                <div className="text-right text-[11px] text-darktext-secondary/70 font-mono">
                  ID: {decision.id.slice(0, 8)}...
                </div>
              </div>

              {/* Opciones Evaluadas */}
              <div>
                <p className="text-[11px] font-semibold text-darktext-secondary uppercase tracking-wider mb-2">
                  Alternativas Evaluadas ({decision.options.length}):
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                  {decision.options.map((opt, idx) => {
                    const isSelected =
                      decision.status === 'decided' && decision.selected_option === opt;

                    return (
                      <div
                        key={idx}
                        className={`p-2.5 rounded-lg text-xs flex items-center justify-between border transition-colors ${
                          isSelected
                            ? 'bg-emerald-950/60 border-brand-emerald/60 text-darktext-primary font-semibold ring-1 ring-brand-emerald/30'
                            : 'bg-dark-elevated border-dark-border text-darktext-secondary'
                        }`}
                      >
                        <span className="truncate" title={opt}>
                          {opt}
                        </span>
                        {isSelected && (
                          <span className="ml-2 flex items-center space-x-1 text-[10px] font-bold text-brand-emerald bg-emerald-900/80 border border-emerald-600/40 px-1.5 py-0.5 rounded">
                            <Check className="w-3 h-3" />
                            <span>Adoptada</span>
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Justificación (Rationale) */}
              {decision.rationale && (
                <div className="p-3 bg-dark-elevated rounded-lg border border-dark-border text-xs text-darktext-primary">
                  <span className="font-semibold text-brand-emerald block mb-0.5">Justificación:</span>
                  <p className="whitespace-pre-wrap text-darktext-secondary">{decision.rationale}</p>
                </div>
              )}

              {/* Metadatos de Resolución y Auditoría */}
              <div className="pt-3 border-t border-dark-border/60 flex flex-wrap items-center justify-between gap-y-2 text-xs text-darktext-secondary">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                  {decision.decided_by && (
                    <span className="inline-flex items-center space-x-1">
                      <User className="w-3.5 h-3.5 text-darktext-secondary" />
                      <span>
                        Resuelto por: <strong className="text-darktext-primary">{decision.decided_by}</strong>
                      </span>
                    </span>
                  )}
                  {decision.decided_at && (
                    <span className="inline-flex items-center space-x-1">
                      <Calendar className="w-3.5 h-3.5 text-darktext-secondary" />
                      <span>Fecha resolución: {formatDate(decision.decided_at)}</span>
                    </span>
                  )}
                </div>

                <div className="text-[11px] text-darktext-secondary/70">
                  Registrado: {formatDate(decision.created_at)}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal para Crear Decisión */}
      <DecisionCreateModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        projectId={projectId}
        defaultDecidedBy={defaultDecidedBy}
        onDecisionCreated={(newDec) => {
          onDecisionCreated(newDec);
          setIsModalOpen(false);
        }}
      />
    </div>
  );
};
