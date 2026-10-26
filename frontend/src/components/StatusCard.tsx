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
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm p-6 max-w-xl w-full">
      <div className="flex items-center justify-between pb-4 border-b border-slate-100">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-slate-100 text-slate-700">
            {isChecking && <RefreshCw className="w-5 h-5 animate-spin text-blue-600" data-testid="icon-checking" />}
            {isAvailable && <CheckCircle2 className="w-5 h-5 text-emerald-600" data-testid="icon-available" />}
            {isUnavailable && <XCircle className="w-5 h-5 text-rose-600" data-testid="icon-unavailable" />}
          </div>
          <div>
            <h3 className="font-semibold text-slate-900 text-base">Estado del Servicio Backend</h3>
            <p className="text-xs text-slate-500">
              Conexión directa con la API REST (FastAPI + PostgreSQL)
            </p>
          </div>
        </div>

        <div>
          {isChecking && (
            <span
              data-testid="status-badge"
              className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200"
            >
              Comprobando
            </span>
          )}
          {isAvailable && (
            <span
              data-testid="status-badge"
              className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200"
            >
              Disponible
            </span>
          )}
          {isUnavailable && (
            <span
              data-testid="status-badge"
              className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200"
            >
              No disponible
            </span>
          )}
        </div>
      </div>

      <div className="py-4 space-y-3">
        {isChecking && (
          <div className="text-sm text-slate-600 flex items-center space-x-2">
            <span className="w-2 h-2 rounded-full bg-blue-500 animate-ping"></span>
            <span>Consultando endpoint <code>GET /api/v1/health</code>...</span>
          </div>
        )}

        {isAvailable && healthData && (
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="bg-slate-50 p-3 rounded-lg border border-slate-100">
              <span className="text-xs text-slate-500 block">Servicio API</span>
              <span className="font-medium text-slate-800 capitalize flex items-center space-x-1 mt-0.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block"></span>
                <span>{healthData.status}</span>
              </span>
            </div>
            <div className="bg-slate-50 p-3 rounded-lg border border-slate-100">
              <span className="text-xs text-slate-500 block">Base de Datos</span>
              <span className="font-medium text-slate-800 capitalize flex items-center space-x-1 mt-0.5">
                <span
                  className={`w-2 h-2 rounded-full inline-block ${
                    healthData.database === 'ok' ? 'bg-emerald-500' : 'bg-amber-500'
                  }`}
                ></span>
                <span>{healthData.database}</span>
              </span>
            </div>
          </div>
        )}

        {isUnavailable && (
          <div className="bg-rose-50 border border-rose-200 p-3.5 rounded-lg text-sm text-rose-800 space-y-1">
            <div className="flex items-center space-x-2 font-medium">
              <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" />
              <span>No se pudo comunicar con el backend</span>
            </div>
            {errorMessage && (
              <p className="text-xs text-rose-700 font-mono break-all pt-1 pl-6">
                {errorMessage}
              </p>
            )}
            <p className="text-xs text-rose-600 pt-1 pl-6">
              Asegúrate de que el servidor FastAPI esté iniciado en <code>http://127.0.0.1:8000</code>.
            </p>
          </div>
        )}

        {lastChecked && (
          <p className="text-xs text-slate-400">
            Última verificación: {lastChecked.toLocaleTimeString()}
          </p>
        )}
      </div>

      <div className="pt-3 border-t border-slate-100 flex justify-end">
        <button
          type="button"
          onClick={onRetry}
          disabled={isChecking}
          className="inline-flex items-center space-x-2 px-3.5 py-2 text-xs font-medium rounded-lg text-slate-700 bg-slate-100 hover:bg-slate-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isChecking ? 'animate-spin' : ''}`} />
          <span>Reintentar comprobación</span>
        </button>
      </div>
    </div>
  );
};
