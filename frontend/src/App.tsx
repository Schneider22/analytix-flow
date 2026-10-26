import React, { useState, useEffect, useCallback } from 'react';
import { getHealth } from './api/health';
import { HealthResponse } from './types/api';
import { StatusCard, ConnectionState } from './components/StatusCard';
import { Layers, ShieldCheck, Database, GitBranch, LayoutDashboard, FileCode2 } from 'lucide-react';

export const App: React.FC = () => {
  const [connectionState, setConnectionState] = useState<ConnectionState>('checking');
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const checkHealth = useCallback(async () => {
    setConnectionState('checking');
    setErrorMessage(null);
    try {
      const data = await getHealth();
      setHealthData(data);
      setConnectionState('available');
    } catch (err: unknown) {
      setHealthData(null);
      setConnectionState('unavailable');
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('Error desconocido al consultar el estado de salud');
      }
    } finally {
      setLastChecked(new Date());
    }
  }, []);

  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      {/* Navbar Superior */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-emerald-600 flex items-center justify-center text-white font-bold text-lg shadow-sm">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <span className="text-lg font-bold text-slate-900 tracking-tight">AnalytixFlow</span>
              <span className="ml-2 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded">
                Business Portal
              </span>
            </div>
          </div>

          <nav className="hidden md:flex items-center space-x-1">
            <button
              type="button"
              className="px-3 py-1.5 text-xs font-semibold rounded-md bg-slate-100 text-slate-800"
            >
              Inicio y Diagnóstico
            </button>
            <div className="flex items-center space-x-1 pl-4 text-xs text-slate-400">
              <span className="px-2 py-1 rounded bg-slate-50 border border-slate-100 text-slate-400">
                M11.3 Proyectos (Próx.)
              </span>
              <span className="px-2 py-1 rounded bg-slate-50 border border-slate-100 text-slate-400">
                M11.4 Ingesta Bronze
              </span>
              <span className="px-2 py-1 rounded bg-slate-50 border border-slate-100 text-slate-400">
                M11.5 Aprobaciones
              </span>
              <span className="px-2 py-1 rounded bg-slate-50 border border-slate-100 text-slate-400">
                M11.6 Dashboard M8
              </span>
            </div>
          </nav>
        </div>
      </header>

      {/* Contenido Principal */}
      <main className="flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full">
        {/* Encabezado Principal */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Portal de Negocio y Gobernanza Analítica
          </h1>
          <p className="mt-1 text-sm text-slate-600 max-w-3xl">
            Entorno interactivo para la gestión rigurosa del ciclo de vida CRISP-DM, compuertas
            humanas obligatorias y verificación criptográfica de linaje.
          </p>
        </div>

        {/* Sección de Estado y Diagnóstico */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
          <div className="lg:col-span-2">
            <StatusCard
              status={connectionState}
              healthData={healthData}
              errorMessage={errorMessage}
              lastChecked={lastChecked}
              onRetry={checkHealth}
            />

            {/* Pilares Arquitectónicos */}
            <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm">
                <div className="flex items-center space-x-2 text-emerald-700 font-semibold text-xs mb-1">
                  <ShieldCheck className="w-4 h-4" />
                  <span>Gobernanza Humana</span>
                </div>
                <p className="text-xs text-slate-600">
                  Compuertas obligatorias para transformaciones materiales, selección de modelos y despliegues.
                </p>
              </div>

              <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm">
                <div className="flex items-center space-x-2 text-blue-700 font-semibold text-xs mb-1">
                  <GitBranch className="w-4 h-4" />
                  <span>Linaje Criptográfico</span>
                </div>
                <p className="text-xs text-slate-600">
                  Trazabilidad punto a punto sellada con hashes SHA-256 canónicos desde el CSV hasta el dashboard.
                </p>
              </div>

              <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm">
                <div className="flex items-center space-x-2 text-amber-700 font-semibold text-xs mb-1">
                  <LayoutDashboard className="w-4 h-4" />
                  <span>Cero Fabricación</span>
                </div>
                <p className="text-xs text-slate-600">
                  Distinción transparente e innegociable entre resultados medidos, estimaciones e hipótesis.
                </p>
              </div>
            </div>
          </div>

          {/* Panel Lateral: Arquitectura Activa */}
          <div className="bg-slate-900 text-slate-200 rounded-xl p-5 shadow-sm text-xs space-y-4">
            <div className="flex items-center space-x-2 pb-3 border-b border-slate-800 text-slate-100 font-semibold">
              <Database className="w-4 h-4 text-emerald-400" />
              <span>Infraestructura Certificada (M10)</span>
            </div>

            <div className="space-y-2">
              <div className="flex justify-between py-1 border-b border-slate-800/60">
                <span className="text-slate-400">Backend API</span>
                <span className="font-mono text-emerald-400">FastAPI (Python)</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800/60">
                <span className="text-slate-400">Base de Datos</span>
                <span className="font-mono text-emerald-400">PostgreSQL 16</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800/60">
                <span className="text-slate-400">Almacén de Artefactos</span>
                <span className="font-mono text-emerald-400">LocalArtifactStore</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-800/60">
                <span className="text-slate-400">Pruebas CI Certificadas</span>
                <span className="font-mono text-emerald-400">138 aprobadas (0 omitidas)</span>
              </div>
            </div>

            <div className="pt-2 text-[11px] text-slate-400">
              <p className="flex items-center space-x-1.5">
                <FileCode2 className="w-3.5 h-3.5 text-slate-500" />
                <span>Frontend: React 18 + Vite + Tailwind CSS</span>
              </p>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 mt-auto py-4">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 gap-2">
          <span>AnalytixFlow v0.1.0 &bull; Incremento 11 (M11.2)</span>
          <span className="font-mono text-slate-400">Commit: d02767b31e990544ee547a44888f6d0942c4ec64</span>
        </div>
      </footer>
    </div>
  );
};

export default App;
