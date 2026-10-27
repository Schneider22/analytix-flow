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
          <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-blue-950/70 text-blue-400 border border-blue-800/60">
            project.created
          </span>
        );
      case 'context.snapshot.created':
        return (
          <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-950/70 text-brand-emerald border border-emerald-800/60">
            context.snapshot.created
          </span>
        );
      case 'decision.created':
        return (
          <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-teal-950/70 text-brand-turquoise border border-teal-800/60">
            decision.created
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-dark-elevated text-darktext-secondary border border-dark-border">
            {action}
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
            <h3 className="text-base font-bold text-darktext-primary">
              Pista de Auditoría y Linaje del Proyecto
            </h3>
            <span
              data-testid="audit-events-count-badge"
              className="px-2 py-0.5 text-xs font-semibold rounded-full bg-dark-elevated text-darktext-secondary border border-dark-border"
            >
              {events.length} {events.length === 1 ? 'evento' : 'eventos'}
            </span>
          </div>
          <p className="text-xs text-darktext-secondary mt-1">
            Registro cronológico inmutable de acciones, actores, correlaciones y hashes del proyecto <span className="font-mono text-darktext-primary">({projectId})</span>.
          </p>
        </div>

        {events.length > 0 && (
          <button
            type="button"
            onClick={() => setSortAscending((prev) => !prev)}
            className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium rounded-lg text-darktext-secondary bg-dark-elevated border border-dark-border hover:bg-dark-card hover:text-darktext-primary transition-colors shadow-sm self-start sm:self-auto"
          >
            <ArrowUpDown className="w-3.5 h-3.5 text-darktext-secondary" />
            <span>{sortAscending ? 'Orden: Más antiguos primero' : 'Orden: Más recientes primero'}</span>
          </button>
        )}
      </div>

      {/* Nota informativa de auditoría */}
      <div className="p-3 bg-amber-950/30 border border-amber-800/50 rounded-xl text-amber-200/90 text-xs flex items-start space-x-2.5">
        <Info className="w-4 h-4 text-brand-warning flex-shrink-0 mt-0.5" />
        <p className="text-[11px] leading-relaxed">
          Los eventos y valores de hash expuestos a continuación reflejan fielmente los registros generados
          por el motor de auditoría del servidor. La interfaz presenta estos metadatos para trazabilidad de
          gobernanza sin efectuar validaciones criptográficas locales autónomas.
        </p>
      </div>

      {/* Estados de Carga y Error */}
      {isLoading && (
        <div data-testid="audit-loading" className="p-8 text-center bg-dark-card rounded-xl border border-dark-border shadow-sm">
          <RefreshCw className="w-6 h-6 animate-spin text-brand-emerald mx-auto mb-2" />
          <p className="text-xs text-darktext-secondary">Consultando pista de auditoría del proyecto...</p>
        </div>
      )}

      {error && !isLoading && (
        <div data-testid="audit-error" className="p-4 bg-red-950/40 border border-brand-error/40 rounded-xl text-red-200 flex items-start space-x-3">
          <AlertTriangle className="w-5 h-5 text-brand-error flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="text-xs font-bold">Error al cargar la pista de auditoría</h4>
            <p className="text-xs mt-0.5">{error}</p>
            <button
              type="button"
              onClick={onRetry}
              className="mt-2 text-xs font-semibold text-brand-error hover:text-red-300 underline inline-flex items-center space-x-1"
            >
              <RefreshCw className="w-3 h-3" />
              <span>Reintentar consulta</span>
            </button>
          </div>
        </div>
      )}

      {/* Estado Vacío */}
      {!isLoading && !error && events.length === 0 && (
        <div data-testid="audit-empty" className="p-8 text-center bg-dark-card rounded-xl border border-dashed border-dark-border">
          <ShieldCheck className="w-10 h-10 text-darktext-secondary/40 mx-auto mb-2" />
          <h4 className="text-sm font-semibold text-darktext-primary">
            Sin eventos de auditoría registrados
          </h4>
          <p className="text-xs text-darktext-secondary max-w-md mx-auto mt-1">
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
              className="bg-dark-card rounded-xl border border-dark-border hover:border-dark-border/80 shadow-xs p-4 space-y-3 transition-all text-xs"
            >
              {/* Encabezado del Evento */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-dark-border/60 pb-2.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-[11px] text-darktext-secondary/60 font-bold">
                    #{index + 1}
                  </span>
                  {renderActionBadge(event.action)}
                  <span className="font-mono text-[11px] text-darktext-secondary bg-dark-elevated px-2 py-0.5 rounded border border-dark-border">
                    {event.entity_type}
                  </span>
                </div>

                <div className="flex items-center space-x-2 text-[11px] text-darktext-secondary">
                  <span className="inline-flex items-center space-x-1">
                    <Calendar className="w-3.5 h-3.5 text-darktext-secondary/70" />
                    <span>{formatDate(event.created_at)}</span>
                  </span>
                </div>
              </div>

              {/* Detalles y Actores */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-darktext-secondary">
                <div>
                  <span className="text-[11px] font-semibold text-darktext-secondary block mb-0.5">
                    Actor y Responsable
                  </span>
                  <div className="flex items-center space-x-1.5 text-darktext-primary">
                    <User className="w-3.5 h-3.5 text-darktext-secondary" />
                    <span className="font-medium">{event.actor_id || 'Sistema / Desconocido'}</span>
                    <span className="text-[10px] text-darktext-secondary/70">({event.actor_type})</span>
                  </div>
                </div>

                <div>
                  <span className="text-[11px] font-semibold text-darktext-secondary block mb-0.5">
                    Correlation ID (Trazabilidad HTTP)
                  </span>
                  <div className="font-mono text-[11px] text-brand-turquoise bg-dark-elevated px-2 py-0.5 rounded border border-dark-border truncate">
                    {event.correlation_id || 'Sin correlación asignada'}
                  </div>
                </div>
              </div>

              {/* Hashes Criptográficos */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                {/* Input Hash */}
                <div>
                  <span className="text-[11px] font-semibold text-darktext-secondary block mb-0.5">
                    Input Hash
                  </span>
                  {event.input_hash ? (
                    <div className="inline-flex items-center justify-between w-full space-x-1.5 px-2.5 py-1 bg-dark-elevated border border-dark-border rounded-lg text-darktext-primary font-mono text-[11px]">
                      <span className="truncate" title={event.input_hash}>
                        <Hash className="w-3 h-3 inline mr-1 text-darktext-secondary" />
                        {event.input_hash.length > 24
                          ? `${event.input_hash.slice(0, 12)}...${event.input_hash.slice(-8)}`
                          : event.input_hash}
                      </span>
                      <button
                        type="button"
                        onClick={() => handleCopyHash(event.input_hash!, `input-${event.id}`)}
                        className="text-darktext-secondary hover:text-darktext-primary p-0.5 transition-colors flex-shrink-0"
                        title="Copiar Input Hash completo"
                        aria-label={`Copiar input hash del evento ${event.id}`}
                      >
                        {copiedHashId === `input-${event.id}` ? (
                          <Check className="w-3.5 h-3.5 text-brand-emerald" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                  ) : (
                    <span className="text-[11px] text-darktext-secondary/60 italic">No aplica (N/A)</span>
                  )}
                </div>

                {/* Output Hash */}
                <div>
                  <span className="text-[11px] font-semibold text-darktext-secondary block mb-0.5">
                    Output Hash
                  </span>
                  {event.output_hash ? (
                    <div className="inline-flex items-center justify-between w-full space-x-1.5 px-2.5 py-1 bg-dark-elevated border border-dark-border rounded-lg text-darktext-primary font-mono text-[11px]">
                      <span className="truncate" title={event.output_hash}>
                        <Hash className="w-3 h-3 inline mr-1 text-darktext-secondary" />
                        {event.output_hash.length > 24
                          ? `${event.output_hash.slice(0, 12)}...${event.output_hash.slice(-8)}`
                          : event.output_hash}
                      </span>
                      <button
                        type="button"
                        onClick={() => handleCopyHash(event.output_hash!, `output-${event.id}`)}
                        className="text-darktext-secondary hover:text-darktext-primary p-0.5 transition-colors flex-shrink-0"
                        title="Copiar Output Hash completo"
                        aria-label={`Copiar output hash del evento ${event.id}`}
                      >
                        {copiedHashId === `output-${event.id}` ? (
                          <Check className="w-3.5 h-3.5 text-brand-emerald" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                  ) : (
                    <span className="text-[11px] text-darktext-secondary/60 italic">No aplica (N/A)</span>
                  )}
                </div>
              </div>

              {/* Metadatos adicionales si existen */}
              {event.metadata && Object.keys(event.metadata).length > 0 && (
                <div className="pt-2 border-t border-dark-border/60 flex flex-wrap items-center gap-1.5">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-darktext-secondary/70 mr-1 flex items-center space-x-1">
                    <Activity className="w-3 h-3 text-darktext-secondary" />
                    <span>Metadatos:</span>
                  </span>
                  {Object.entries(event.metadata).map(([key, val]) => (
                    <span
                      key={key}
                      className="px-2 py-0.5 bg-dark-elevated text-darktext-secondary text-[10px] font-mono rounded border border-dark-border/60"
                    >
                      {key}: <strong className="text-darktext-primary">{String(val)}</strong>
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
