import React from 'react';
import { HealthResponse } from '../types/api';
import { CheckCircle2, AlertTriangle, XCircle, RefreshCw } from 'lucide-react';

export type ConnectionState = 'checking' | 'available' | 'unavailable';

interface StatusCardProps {
  status: ConnectionState;
  healthData: HealthResponse | null;
  errorMessage: string | null;
  lastChecked: Date | null;
  onRetry: () => void;
}

export const StatusCard: React.FC<StatusCardProps> = ({
  status,
  healthData,
  errorMessage,
  lastChecked,
  onRetry,
}) => {
  const isChecking = status === 'checking';
  const isAvailable = status === 'available';
  const isUnavailable = status === 'unavailable';

  return (
    <div className="bg-dark-card border border-dark-border rounded-xl shadow-lg p-6 max-w-xl w-full">
      <div className="flex items-center justify-between pb-4 border-b border-dark-border">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-dark-elevated border border-dark-border">
            {isChecking && <RefreshCw className="w-5 h-5 animate-spin text-brand-turquoise" data-testid="icon-checking" />}
            {isAvailable && <CheckCircle2 className="w-5 h-5 text-brand-emerald" data-testid="icon-available" />}
            {isUnavailable && <XCircle className="w-5 h-5 text-brand-error" data-testid="icon-unavailable" />}
          </div>
          <div>
            <h3 className="font-semibold text-darktext-primary text-base">Estado del Servicio Backend</h3>
            <p className="text-xs text-darktext-secondary">
              Conexión directa con la API REST (FastAPI + PostgreSQL)
            </p>
          </div>
        </div>

        <div>
          {isChecking && (
            <span
              data-testid="status-badge"
              className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-cyan-950/70 text-brand-turquoise border border-cyan-700/50"
            >
              Comprobando
            </span>
          )}
          {isAvailable && (
            <span
              data-testid="status-badge"
              className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-950/70 text-brand-emerald border border-emerald-700/50"
            >
              Disponible
            </span>
          )}
          {isUnavailable && (
            <span
              data-testid="status-badge"
              className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-950/70 text-brand-error border border-rose-800/50"
            >
              No disponible
            </span>
          )}
        </div>
      </div>

      <div className="py-4 space-y-3">
        {isChecking && (
          <div className="text-sm text-darktext-secondary flex items-center space-x-2">
            <span className="w-2 h-2 rounded-full bg-brand-turquoise animate-ping"></span>
            <span>Consultando endpoint <code className="text-brand-turquoise font-mono bg-dark-elevated px-1.5 py-0.5 rounded border border-dark-border">GET /api/v1/health</code>...</span>
          </div>
        )}

        {isAvailable && healthData && (
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="bg-dark-elevated p-3 rounded-lg border border-dark-border">
              <span className="text-xs text-darktext-secondary block">Servicio API</span>
              <span className="font-medium text-darktext-primary capitalize flex items-center space-x-1.5 mt-0.5">
                <span className="w-2 h-2 rounded-full bg-brand-emerald inline-block"></span>
                <span>{healthData.status}</span>
              </span>
            </div>
            <div className="bg-dark-elevated p-3 rounded-lg border border-dark-border">
              <span className="text-xs text-darktext-secondary block">Base de Datos</span>
              <span className="font-medium text-darktext-primary capitalize flex items-center space-x-1.5 mt-0.5">
                <span
                  className={`w-2 h-2 rounded-full inline-block ${
                    healthData.database === 'ok' ? 'bg-brand-emerald' : 'bg-brand-warning'
                  }`}
                ></span>
                <span>{healthData.database}</span>
              </span>
            </div>
          </div>
        )}

        {isUnavailable && (
          <div className="bg-rose-950/30 border border-brand-error/40 p-3.5 rounded-lg text-sm text-darktext-primary space-y-1">
            <div className="flex items-center space-x-2 font-medium text-brand-error">
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
              <span>No se pudo comunicar con el backend</span>
            </div>
            {errorMessage && (
              <p className="text-xs text-rose-300 font-mono break-all pt-1 pl-6">
                {errorMessage}
              </p>
            )}
            <p className="text-xs text-darktext-secondary pt-1 pl-6">
              Asegúrate de que el servidor FastAPI esté iniciado en <code className="text-brand-turquoise font-mono bg-dark-elevated px-1 py-0.5 rounded">http://127.0.0.1:8000</code>.
            </p>
          </div>
        )}

        {lastChecked && (
          <p className="text-xs text-darktext-secondary/70">
            Última verificación: {lastChecked.toLocaleTimeString()}
          </p>
        )}
      </div>

      <div className="pt-3 border-t border-dark-border flex justify-end">
        <button
          type="button"
          onClick={onRetry}
          disabled={isChecking}
          className="inline-flex items-center space-x-2 px-3.5 py-2 text-xs font-semibold rounded-lg text-darktext-primary bg-dark-elevated hover:bg-dark-border disabled:opacity-50 disabled:cursor-not-allowed transition-colors border border-dark-border"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isChecking ? 'animate-spin' : ''}`} />
          <span>Reintentar comprobación</span>
        </button>
      </div>
    </div>
  );
};
