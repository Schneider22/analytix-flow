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
}

export const DecisionList: React.FC<DecisionListProps> = ({
  projectId,
  decisions,
  isLoading,
  error,
  onRetry,
  onDecisionCreated,
  defaultDecidedBy,
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
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Decidida</span>
          </span>
        );
      case 'pending':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 text-xs font-semibold rounded-full bg-amber-100 text-amber-800 border border-amber-200">
            <Clock className="w-3.5 h-3.5" />
            <span>Pendiente</span>
          </span>
        );
      case 'rejected':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 text-xs font-semibold rounded-full bg-rose-100 text-rose-800 border border-rose-200">
            <XCircle className="w-3.5 h-3.5" />
            <span>Rechazada</span>
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-0.5 text-xs font-medium rounded-full bg-slate-100 text-slate-700">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Cabecera de la sección */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center space-x-2">
            <h3 className="text-base font-bold text-slate-900">Decisiones de Negocio</h3>
            <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-slate-100 text-slate-700 border border-slate-200">
              {decisions.length} {decisions.length === 1 ? 'decisión' : 'decisiones'}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Registro auditable de alternativas evaluadas, justificaciones y opciones analíticas adoptadas.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setIsModalOpen(true)}
          className="inline-flex items-center justify-center space-x-1.5 px-3.5 py-2 text-xs font-semibold rounded-lg text-white bg-indigo-600 hover:bg-indigo-700 transition-colors shadow-sm self-start sm:self-auto"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Registrar Decisión</span>
        </button>
      </div>

      {/* Estados de Carga y Error */}
      {isLoading && (
        <div className="p-8 text-center bg-white rounded-xl border border-slate-200 shadow-sm">
          <RefreshCw className="w-6 h-6 animate-spin text-indigo-600 mx-auto mb-2" />
          <p className="text-xs text-slate-600">Cargando decisiones de negocio...</p>
        </div>
      )}

      {error && !isLoading && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 flex items-start space-x-3">
          <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="text-xs font-bold">Error al cargar las decisiones de negocio</h4>
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
      {!isLoading && !error && decisions.length === 0 && (
        <div className="p-8 text-center bg-white rounded-xl border border-dashed border-slate-300">
          <Scale className="w-10 h-10 text-slate-300 mx-auto mb-2" />
          <h4 className="text-sm font-semibold text-slate-800">
            Sin decisiones de negocio registradas
          </h4>
          <p className="text-xs text-slate-500 max-w-md mx-auto mt-1 mb-4">
            No se han formalizado decisiones ni selección de alternativas para este proyecto.
            Puedes registrar una nueva decisión o usar la plantilla estándar M1.
          </p>
          <button
            type="button"
            onClick={() => setIsModalOpen(true)}
            className="inline-flex items-center space-x-1.5 px-3.5 py-2 text-xs font-semibold rounded-lg text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Registrar Primera Decisión</span>
          </button>
        </div>
      )}

      {/* Listado de Decisiones */}
      {!isLoading && !error && decisions.length > 0 && (
        <div className="space-y-4">
          {decisions.map((decision) => (
            <div
              key={decision.id}
              className="bg-white rounded-xl border border-slate-200 hover:border-slate-300 shadow-xs p-5 space-y-4 transition-all"
            >
              {/* Cabecera de la Decisión */}
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    {renderStatusBadge(decision.status)}
                    <span className="px-2 py-0.5 text-[11px] font-mono font-medium rounded-md bg-slate-100 text-slate-700 border border-slate-200">
                      {decision.decision_type}
                    </span>
                  </div>
                  <h4 className="text-sm font-bold text-slate-900 pt-1">{decision.question}</h4>
                </div>

                <div className="text-right text-[11px] text-slate-400 font-mono">
                  ID: {decision.id.slice(0, 8)}...
                </div>
              </div>

              {/* Opciones Evaluadas */}
              <div>
                <p className="text-[11px] font-semibold text-slate-600 uppercase tracking-wider mb-2">
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
                            ? 'bg-emerald-50 border-emerald-300 text-emerald-950 font-semibold ring-1 ring-emerald-200'
                            : 'bg-slate-50 border-slate-200 text-slate-700'
                        }`}
                      >
                        <span className="truncate" title={opt}>
                          {opt}
                        </span>
                        {isSelected && (
                          <span className="ml-2 flex items-center space-x-1 text-[10px] font-bold text-emerald-700 bg-emerald-100 px-1.5 py-0.5 rounded">
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
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-700">
                  <span className="font-semibold text-slate-900 block mb-0.5">Justificación:</span>
                  <p className="whitespace-pre-wrap">{decision.rationale}</p>
                </div>
              )}

              {/* Metadatos de Resolución y Auditoría */}
              <div className="pt-3 border-t border-slate-100 flex flex-wrap items-center justify-between gap-y-2 text-xs text-slate-500">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                  {decision.decided_by && (
                    <span className="inline-flex items-center space-x-1">
                      <User className="w-3.5 h-3.5 text-slate-400" />
                      <span>
                        Resuelto por: <strong className="text-slate-700">{decision.decided_by}</strong>
                      </span>
                    </span>
                  )}
                  {decision.decided_at && (
                    <span className="inline-flex items-center space-x-1">
                      <Calendar className="w-3.5 h-3.5 text-slate-400" />
                      <span>Fecha resolución: {formatDate(decision.decided_at)}</span>
                    </span>
                  )}
                </div>

                <div className="text-[11px] text-slate-400">
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
