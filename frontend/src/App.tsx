import React, { useState, useEffect, useCallback } from 'react';
import { getHealth } from './api/health';
import { listProjects } from './api/projects';
import { HealthResponse } from './types/api';
import { ProjectRead } from './types/projects';
import { StatusCard, ConnectionState } from './components/StatusCard';
import { ProjectList } from './components/projects/ProjectList';
import { ProjectCreateModal } from './components/projects/ProjectCreateModal';
import { ProjectDetail } from './components/projects/ProjectDetail';
import {
  Layers,
  ShieldCheck,
  Database,
  GitBranch,
  LayoutDashboard,
  FileCode2,
  FolderKanban,
  Activity,
} from 'lucide-react';

export type ActiveView = 'diagnostics' | 'projects' | 'project-detail';

export const App: React.FC = () => {
  // Estado de navegación
  const [activeView, setActiveView] = useState<ActiveView>('projects');
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  // Estado de Salud (M11.2)
  const [connectionState, setConnectionState] = useState<ConnectionState>('checking');
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);
  const [healthErrorMessage, setHealthErrorMessage] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  // Estado de Proyectos (M11.3A)
  const [projects, setProjects] = useState<ProjectRead[]>([]);
  const [isLoadingProjects, setIsLoadingProjects] = useState(false);
  const [projectsErrorMessage, setProjectsErrorMessage] = useState<string | null>(null);

  const checkHealth = useCallback(async () => {
    setConnectionState('checking');
    setHealthErrorMessage(null);
    try {
      const data = await getHealth();
      setHealthData(data);
      setConnectionState('available');
    } catch (err: unknown) {
      setHealthData(null);
      setConnectionState('unavailable');
      if (err instanceof Error) {
        setHealthErrorMessage(err.message);
      } else {
        setHealthErrorMessage('Error desconocido al consultar el estado de salud');
      }
    } finally {
      setLastChecked(new Date());
    }
  }, []);

  const fetchProjects = useCallback(async () => {
    setIsLoadingProjects(true);
    setProjectsErrorMessage(null);
    try {
      const data = await listProjects();
      setProjects(data);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setProjectsErrorMessage(err.message);
      } else {
        setProjectsErrorMessage('Error al consultar la lista de proyectos');
      }
    } finally {
      setIsLoadingProjects(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    fetchProjects();
  }, [checkHealth, fetchProjects]);

  const handleSelectProject = (projectId: string) => {
    setSelectedProjectId(projectId);
    setActiveView('project-detail');
  };

  const handleProjectCreated = (newProject: ProjectRead) => {
    setProjects((prev) => [newProject, ...prev]);
    setSelectedProjectId(newProject.id);
    setActiveView('project-detail');
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      {/* Navbar Superior */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-40">
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

          <nav className="hidden md:flex items-center space-x-2">
            <button
              type="button"
              onClick={() => setActiveView('projects')}
              className={`inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                activeView === 'projects' || activeView === 'project-detail'
                  ? 'bg-emerald-50 text-emerald-800 border border-emerald-200 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <FolderKanban className="w-4 h-4" />
              <span>Proyectos y Negocio (M1)</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveView('diagnostics')}
              className={`inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
                activeView === 'diagnostics'
                  ? 'bg-slate-100 text-slate-900 border border-slate-200 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <Activity className="w-4 h-4" />
              <span>Diagnóstico de Salud</span>
            </button>

            <div className="flex items-center space-x-1 pl-3 text-xs text-slate-400 border-l border-slate-200">
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
        {/* Vista 1: Listado de Proyectos (M11.3A) */}
        {activeView === 'projects' && (
          <ProjectList
            projects={projects}
            isLoading={isLoadingProjects}
            errorMessage={projectsErrorMessage}
            onRefresh={fetchProjects}
            onSelectProject={handleSelectProject}
            onOpenCreateModal={() => setIsCreateModalOpen(true)}
          />
        )}

        {/* Vista 2: Detalle de Proyecto (M11.3A) */}
        {activeView === 'project-detail' && selectedProjectId && (
          <ProjectDetail
            projectId={selectedProjectId}
            onBack={() => {
              setActiveView('projects');
              fetchProjects();
            }}
          />
        )}

        {/* Vista 3: Diagnóstico y Salud del Sistema (M11.2) */}
        {activeView === 'diagnostics' && (
          <div className="space-y-8">
            <div>
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
                Portal de Negocio y Gobernanza Analítica
              </h1>
              <p className="mt-1 text-sm text-slate-600 max-w-3xl">
                Diagnóstico en tiempo real de la conectividad con la API de FastAPI y la persistencia PostgreSQL.
              </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
              <div className="lg:col-span-2">
                <StatusCard
                  status={connectionState}
                  healthData={healthData}
                  errorMessage={healthErrorMessage}
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
                      Trazabilidad sellada con hashes SHA-256 canónicos desde el CSV hasta el dashboard.
                    </p>
                  </div>

                  <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm">
                    <div className="flex items-center space-x-2 text-amber-700 font-semibold text-xs mb-1">
                      <LayoutDashboard className="w-4 h-4" />
                      <span>Cero Fabricación</span>
                    </div>
                    <p className="text-xs text-slate-600">
                      Distinción transparente entre resultados medidos, estimaciones e hipótesis.
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
          </div>
        )}
      </main>

      {/* Modal de Creación de Proyectos */}
      <ProjectCreateModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onProjectCreated={handleProjectCreated}
      />

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 mt-auto py-4">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between text-xs text-slate-500 gap-2">
          <span>AnalytixFlow v0.1.0 &bull; Incremento 11 (M11.3A)</span>
          <span className="font-mono text-slate-400">Commit Base: 2d652c90a6e803319e92bd0c280ae7991c4f2196</span>
        </div>
      </footer>
    </div>
  );
};

export default App;
