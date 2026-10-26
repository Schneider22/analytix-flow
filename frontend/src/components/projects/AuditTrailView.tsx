import React, { useState } from 'react';
import { AuditEventRead } from '../../types/projects';
import {
  ShieldCheck,
  RefreshCw,
  AlertTriangle,
  Copy,
  Check,
  ArrowUpDown,
  User,
  Calendar,
  Hash,
  Activity,
  Info,
} from 'lucide-react';

interface AuditTrailViewProps {
  projectId: string;
  events: AuditEventRead[];
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
}

export const AuditTrailView: React.FC<AuditTrailViewProps> = ({
  projectId,
  events,
  isLoading,
  error,
  onRetry,
}) => {
  const [sortAscending, setSortAscending] = useState(true);
  const [copiedHashId, setCopiedHashId] = useState<string | null>(null);

  // Sorting: backend returns descending. Presentation can sort chronological (ascending) by default
  const sortedEvents = [...events].sort((a, b) => {
    const timeA = new Date(a.created_at).getTime();
    const timeB = new Date(b.created_at).getTime();
    return sortAscending ? timeA - timeB : timeB - timeA;
  });

  const handleCopyHash = async (hashValue: string, keyId: string) => {
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(hashValue);
        setCopiedHashId(keyId);
        setTimeout(() => setCopiedHashId(null), 2000);
      }
    } catch {
      // Fallback
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
        second: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  const renderActionBadge = (action: string) => {
    switch (action) {
      case 'project.created':
        return (
          <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-blue-100 text-blue-800 border border-blue-200">
            project.created
          </span>
        );
      case 'context.snapshot.created':
        return (
          <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
            context.snapshot.created
          </span>
        );
      case 'decision.created':
        return (
          <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-indigo-100 text-indigo-800 border border-indigo-200">
            decision.created
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-slate-100 text-slate-700 border border-slate-200">
            {action}
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
            <h3 className="text-base font-bold text-slate-900">
              Pista de Auditoría y Linaje del Proyecto
            </h3>
            <span
              data-testid="audit-events-count-badge"
              className="px-2 py-0.5 text-xs font-semibold rounded-full bg-slate-100 text-slate-700 border border-slate-200"
            >
              {events.length} {events.length === 1 ? 'evento' : 'eventos'}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Registro cronológico inmutable de acciones, actores, correlaciones y hashes del proyecto <span className="font-mono text-slate-600">({projectId})</span>.
          </p>
        </div>

        {events.length > 0 && (
          <button
            type="button"
            onClick={() => setSortAscending((prev) => !prev)}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium rounded-lg text-slate-700 bg-white border border-slate-300 hover:bg-slate-50 transition-colors shadow-sm self-start sm:self-auto"
          >
            <ArrowUpDown className="w-3.5 h-3.5 text-slate-500" />
            <span>{sortAscending ? 'Orden: Más antiguos primero' : 'Orden: Más recientes primero'}</span>
          </button>
        )}
      </div>

      {/* Nota informativa de auditoría */}
      <div className="p-3 bg-amber-50/70 border border-amber-200 rounded-xl text-amber-900 text-xs flex items-start space-x-2.5">
        <Info className="w-4 h-4 text-amber-700 flex-shrink-0 mt-0.5" />
        <p className="text-[11px] leading-relaxed">
          Los eventos y valores de hash expuestos a continuación reflejan fielmente los registros generados
          por el motor de auditoría del servidor. La interfaz presenta estos metadatos para trazabilidad de
          gobernanza sin efectuar validaciones criptográficas locales autónomas.
        </p>
      </div>

      {/* Estados de Carga y Error */}
      {isLoading && (
        <div data-testid="audit-loading" className="p-8 text-center bg-white rounded-xl border border-slate-200 shadow-sm">
          <RefreshCw className="w-6 h-6 animate-spin text-emerald-600 mx-auto mb-2" />
          <p className="text-xs text-slate-600">Consultando pista de auditoría del proyecto...</p>
        </div>
      )}

      {error && !isLoading && (
        <div data-testid="audit-error" className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 flex items-start space-x-3">
          <AlertTriangle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="text-xs font-bold">Error al cargar la pista de auditoría</h4>
            <p className="text-xs mt-0.5">{error}</p>
            <button
              type="button"
              onClick={onRetry}
              className="mt-2 text-xs font-semibold text-rose-700 hover:text-rose-900 underline inline-flex items-center space-x-1"
            >
              <RefreshCw className="w-3 h-3" />
              <span>Reintentar consulta</span>
            </button>
          </div>
        </div>
      )}

      {/* Estado Vacío */}
      {!isLoading && !error && events.length === 0 && (
        <div data-testid="audit-empty" className="p-8 text-center bg-white rounded-xl border border-dashed border-slate-300">
          <ShieldCheck className="w-10 h-10 text-slate-300 mx-auto mb-2" />
          <h4 className="text-sm font-semibold text-slate-800">
            Sin eventos de auditoría registrados
          </h4>
          <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
            No se han registrado eventos auditables para este proyecto en el servidor.
          </p>
        </div>
      )}

      {/* Lista de Eventos de Auditoría */}
      {!isLoading && !error && events.length > 0 && (
        <div className="space-y-3">
          {sortedEvents.map((event, index) => (
            <div
              key={event.id}
              className="bg-white rounded-xl border border-slate-200 hover:border-slate-300 shadow-xs p-4 space-y-3 transition-all text-xs"
            >
              {/* Encabezado del Evento */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-2.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-[11px] text-slate-400 font-bold">
                    #{index + 1}
                  </span>
                  {renderActionBadge(event.action)}
                  <span className="font-mono text-[11px] text-slate-500 bg-slate-50 px-2 py-0.5 rounded border border-slate-200">
                    {event.entity_type}
                  </span>
                </div>

                <div className="flex items-center space-x-2 text-[11px] text-slate-500">
                  <span className="inline-flex items-center space-x-1">
                    <Calendar className="w-3.5 h-3.5 text-slate-400" />
                    <span>{formatDate(event.created_at)}</span>
                  </span>
                </div>
              </div>

              {/* Detalles y Actores */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-slate-600">
                <div>
                  <span className="text-[11px] font-semibold text-slate-500 block mb-0.5">
                    Actor y Responsable
                  </span>
                  <div className="flex items-center space-x-1.5 text-slate-800">
                    <User className="w-3.5 h-3.5 text-slate-400" />
                    <span className="font-medium">{event.actor_id || 'Sistema / Desconocido'}</span>
                    <span className="text-[10px] text-slate-400">({event.actor_type})</span>
                  </div>
                </div>

                <div>
                  <span className="text-[11px] font-semibold text-slate-500 block mb-0.5">
                    Correlation ID (Trazabilidad HTTP)
                  </span>
                  <div className="font-mono text-[11px] text-slate-700 bg-slate-50 px-2 py-0.5 rounded border border-slate-200 truncate">
                    {event.correlation_id || 'Sin correlación asignada'}
                  </div>
                </div>
              </div>

              {/* Hashes Criptográficos */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                {/* Input Hash */}
                <div>
                  <span className="text-[11px] font-semibold text-slate-500 block mb-0.5">
                    Input Hash
                  </span>
                  {event.input_hash ? (
                    <div className="inline-flex items-center justify-between w-full space-x-1.5 px-2.5 py-1 bg-slate-50 border border-slate-200 rounded-lg text-slate-700 font-mono text-[11px]">
                      <span className="truncate" title={event.input_hash}>
                        <Hash className="w-3 h-3 inline mr-1 text-slate-400" />
                        {event.input_hash.length > 24
                          ? `${event.input_hash.slice(0, 12)}...${event.input_hash.slice(-8)}`
                          : event.input_hash}
                      </span>
                      <button
                        type="button"
                        onClick={() => handleCopyHash(event.input_hash!, `input-${event.id}`)}
                        className="text-slate-400 hover:text-slate-700 p-0.5 transition-colors flex-shrink-0"
                        title="Copiar Input Hash completo"
                        aria-label={`Copiar input hash del evento ${event.id}`}
                      >
                        {copiedHashId === `input-${event.id}` ? (
                          <Check className="w-3.5 h-3.5 text-emerald-600" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                  ) : (
                    <span className="text-[11px] text-slate-400 italic">No aplica (N/A)</span>
                  )}
                </div>

                {/* Output Hash */}
                <div>
                  <span className="text-[11px] font-semibold text-slate-500 block mb-0.5">
                    Output Hash
                  </span>
                  {event.output_hash ? (
                    <div className="inline-flex items-center justify-between w-full space-x-1.5 px-2.5 py-1 bg-slate-50 border border-slate-200 rounded-lg text-slate-700 font-mono text-[11px]">
                      <span className="truncate" title={event.output_hash}>
                        <Hash className="w-3 h-3 inline mr-1 text-slate-400" />
                        {event.output_hash.length > 24
                          ? `${event.output_hash.slice(0, 12)}...${event.output_hash.slice(-8)}`
                          : event.output_hash}
                      </span>
                      <button
                        type="button"
                        onClick={() => handleCopyHash(event.output_hash!, `output-${event.id}`)}
                        className="text-slate-400 hover:text-slate-700 p-0.5 transition-colors flex-shrink-0"
                        title="Copiar Output Hash completo"
                        aria-label={`Copiar output hash del evento ${event.id}`}
                      >
                        {copiedHashId === `output-${event.id}` ? (
                          <Check className="w-3.5 h-3.5 text-emerald-600" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                  ) : (
                    <span className="text-[11px] text-slate-400 italic">No aplica (N/A)</span>
                  )}
                </div>
              </div>

              {/* Metadatos adicionales si existen */}
              {event.metadata && Object.keys(event.metadata).length > 0 && (
                <div className="pt-2 border-t border-slate-100 flex flex-wrap items-center gap-1.5">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mr-1 flex items-center space-x-1">
                    <Activity className="w-3 h-3 text-slate-400" />
                    <span>Metadatos:</span>
                  </span>
                  {Object.entries(event.metadata).map(([key, val]) => (
                    <span
                      key={key}
                      className="px-2 py-0.5 bg-slate-100 text-slate-700 text-[10px] font-mono rounded"
                    >
                      {key}: <strong className="text-slate-900">{String(val)}</strong>
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
