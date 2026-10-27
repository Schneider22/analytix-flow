import React, { useState, useEffect, useCallback } from 'react';
import { getHealth } from './api/health';
import { listProjects } from './api/projects';
import { HealthResponse } from './types/api';
import { ProjectArchiveFilter, ProjectRead } from './types/projects';
import { StatusCard, ConnectionState } from './components/StatusCard';
import { ProjectList } from './components/projects/ProjectList';
import { ProjectCreateModal } from './components/projects/ProjectCreateModal';
import { ProjectDetail } from './components/projects/ProjectDetail';
import { BrandLogo } from './components/brand/BrandLogo';
import {
  ShieldCheck,
  Database,
  GitBranch,
  LayoutDashboard,
  FileCode2,
  FolderKanban,
  Activity,
  Layers,
  Menu,
  X,
  ChevronRight,
} from 'lucide-react';

export type ActiveView = 'diagnostics' | 'projects' | 'project-detail';

export const App: React.FC = () => {
  const [activeView, setActiveView] = useState<ActiveView>('projects');
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const [connectionState, setConnectionState] = useState<ConnectionState>('checking');
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);
  const [healthErrorMessage, setHealthErrorMessage] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const [projects, setProjects] = useState<ProjectRead[]>([]);
  const [archiveFilter, setArchiveFilter] = useState<ProjectArchiveFilter>('exclude');
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
      const data = await listProjects({ archived: archiveFilter });
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
  }, [archiveFilter]);

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

  /* ─── Sidebar status dot ─── */
  const statusDot = (
    <span
      className={`w-2 h-2 rounded-full flex-shrink-0 ${
        connectionState === 'available'
          ? 'bg-brand-emerald shadow-[0_0_6px_rgba(16,185,129,0.8)]'
          : connectionState === 'checking'
          ? 'bg-brand-warning animate-pulse'
          : 'bg-brand-error'
      }`}
    />
  );

  /* ─── Shared nav items ─── */
  const renderNav = (mobile = false) => (
    <nav className="flex-1 py-4 overflow-y-auto">
      {/* Active modules section */}
      <div className="px-3 mb-1">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-darktext-secondary/60 px-2 mb-2">
          Plataforma
        </p>

        <button
          type="button"
          onClick={() => { setActiveView('projects'); if (mobile) setMobileMenuOpen(false); }}
          className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm font-medium transition-all ${
            activeView === 'projects' || activeView === 'project-detail'
              ? 'bg-dark-elevated text-brand-turquoise border-l-2 border-brand-turquoise pl-[10px]'
              : 'text-darktext-secondary hover:bg-dark-elevated hover:text-darktext-primary border-l-2 border-transparent pl-[10px]'
          }`}
        >
          <FolderKanban className="w-4 h-4 flex-shrink-0" />
          <span className="flex-1 text-left">Proyectos y Negocio (M1)</span>
          <span className="ml-auto text-[10px] font-mono bg-dark-border rounded px-1.5 py-0.5 text-darktext-secondary">
            {projects.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => { setActiveView('diagnostics'); if (mobile) setMobileMenuOpen(false); }}
          className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm font-medium transition-all mt-0.5 ${
            activeView === 'diagnostics'
              ? 'bg-dark-elevated text-brand-turquoise border-l-2 border-brand-turquoise pl-[10px]'
              : 'text-darktext-secondary hover:bg-dark-elevated hover:text-darktext-primary border-l-2 border-transparent pl-[10px]'
          }`}
        >
          <Activity className="w-4 h-4 flex-shrink-0" />
          <span className="flex-1 text-left">Diagnóstico de Servicios</span>
          {statusDot}
        </button>
      </div>

      {/* Upcoming modules */}
      <div className="px-3 mt-4">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-darktext-secondary/60 px-2 mb-2">
          Próximos módulos
        </p>

        {[
          { icon: <Layers className="w-4 h-4" />, label: 'M11.4 Ingesta Bronze' },
          { icon: <ShieldCheck className="w-4 h-4" />, label: 'M11.5 Aprobaciones' },
          { icon: <LayoutDashboard className="w-4 h-4" />, label: 'M11.6 Dashboard M8' },
        ].map(({ icon, label }) => (
          <div
            key={label}
            className="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm text-darktext-secondary/40 border-l-2 border-transparent pl-[10px] cursor-default select-none"
          >
            <span className="opacity-50 flex-shrink-0">{icon}</span>
            <span className="flex-1">{label}</span>
            <span className="text-[9px] font-mono bg-dark-border/60 border border-dark-border rounded px-1.5 py-0.5 text-darktext-secondary/40">
              Soon
            </span>
          </div>
        ))}
      </div>
    </nav>
  );

  /* ─── Sidebar footer ─── */
  const renderFooter = () => (
    <div className="border-t border-dark-border p-4 space-y-1.5 text-[11px]">
      <div className="flex items-center justify-between text-darktext-secondary">
        <span>Portal</span>
        <span className="font-mono text-brand-turquoise">v0.1.0</span>
      </div>
      <div className="flex items-center justify-between text-darktext-secondary">
        <span>Incr.</span>
        <span className="font-mono text-brand-emerald">M11.3C</span>
      </div>
      <div className="flex items-center justify-between text-darktext-secondary">
        <span>Entorno</span>
        <span className="font-mono text-darktext-primary/70">Local / PG</span>
      </div>
    </div>
  );

  /* ─── View breadcrumb label ─── */
  const viewLabel =
    activeView === 'projects' ? 'Proyectos'
    : activeView === 'project-detail' ? 'Ficha de Proyecto'
    : 'Diagnóstico de Servicios';

  return (
    <div className="min-h-screen bg-dark-primary text-darktext-primary flex font-sans antialiased selection:bg-brand-turquoise/20 selection:text-brand-turquoise">

      {/* ════════════════════════════════════════
          SIDEBAR — desktop
      ════════════════════════════════════════ */}
      <aside aria-label="Navegación principal" className="hidden md:flex md:w-60 xl:w-64 flex-shrink-0 h-screen sticky top-0 bg-dark-secondary border-r border-dark-border flex-col z-30">
        {/* Brand header */}
        <div className="flex flex-col px-4 py-4 border-b border-dark-border gap-2">
          <BrandLogo variant="compact" size="sm" showSlogan={false} />
          <span className="text-[10px] font-semibold text-brand-turquoise bg-dark-elevated border border-dark-border px-2 py-0.5 rounded-full w-fit">
            Business Portal
          </span>
        </div>

        {/* Nav */}
        {renderNav(false)}

        {/* Footer metadata */}
        {renderFooter()}
      </aside>

      {/* ════════════════════════════════════════
          MOBILE DRAWER
      ════════════════════════════════════════ */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/70 backdrop-blur-sm"
            onClick={() => setMobileMenuOpen(false)}
            aria-hidden="true"
          />
          {/* Drawer */}
          <aside className="relative w-64 max-w-[85vw] h-full bg-dark-secondary border-r border-dark-border flex flex-col z-10 shadow-2xl">
            <div className="flex items-center justify-between px-4 py-4 border-b border-dark-border">
              <BrandLogo variant="compact" size="sm" />
              <button
                type="button"
                onClick={() => setMobileMenuOpen(false)}
                aria-label="Cerrar menú"
                className="p-1.5 rounded-md text-darktext-secondary hover:bg-dark-elevated hover:text-darktext-primary transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            {renderNav(true)}
            {renderFooter()}
          </aside>
        </div>
      )}

      {/* ════════════════════════════════════════
          MAIN CONTENT AREA
      ════════════════════════════════════════ */}
      <div className="flex-1 flex flex-col min-w-0 min-h-screen">

        {/* ── Top content header ── */}
        <header className="h-14 bg-dark-secondary/80 backdrop-blur-md border-b border-dark-border sticky top-0 z-20 flex items-center justify-between px-4 sm:px-6">
          {/* Left: hamburger + breadcrumb */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              aria-label="Abrir menú de navegación"
              className="md:hidden p-1.5 rounded-md text-darktext-secondary hover:bg-dark-elevated hover:text-darktext-primary transition-colors"
            >
              <Menu className="w-4 h-4" />
            </button>
            <nav aria-label="Ruta de navegación" className="flex items-center gap-1.5 text-xs">
              <span className="text-darktext-secondary">Plataforma</span>
              <ChevronRight className="w-3.5 h-3.5 text-darktext-secondary/40" />
              <span className="font-semibold text-darktext-primary">{viewLabel}</span>
            </nav>
          </div>

          {/* Right: connection status + user */}
          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 text-xs text-darktext-secondary border border-dark-border rounded-full px-3 py-1">
              {statusDot}
              <span className="font-mono text-[11px]">
                {connectionState === 'available' ? 'PostgreSQL OK'
                  : connectionState === 'checking' ? 'Verificando…'
                  : 'Sin conexión'}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-gradient-to-br from-brand-turquoise to-brand-emerald flex items-center justify-center text-dark-primary font-bold text-[11px] shadow-sm">
                CD
              </div>
              <div className="hidden lg:block text-left">
                <p className="text-xs font-semibold text-darktext-primary leading-none">Lead Architect</p>
                <p className="text-[10px] text-darktext-secondary leading-none mt-0.5">CDO / Gobernanza</p>
              </div>
            </div>
          </div>
        </header>

        {/* ── Content body ── */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-screen-xl w-full mx-auto">

          {activeView === 'projects' && (
            <ProjectList
              projects={projects}
              isLoading={isLoadingProjects}
              errorMessage={projectsErrorMessage}
              onRefresh={fetchProjects}
              onSelectProject={handleSelectProject}
              onOpenCreateModal={() => setIsCreateModalOpen(true)}
              archiveFilter={archiveFilter}
              onArchiveFilterChange={setArchiveFilter}
            />
          )}

          {activeView === 'project-detail' && selectedProjectId && (
            <ProjectDetail
              projectId={selectedProjectId}
              onBack={() => {
                setActiveView('projects');
                fetchProjects();
              }}
            />
          )}

          {activeView === 'diagnostics' && (
            <div className="space-y-8">
              <div>
                <h1 className="text-xl font-bold text-darktext-primary tracking-tight">
                  Diagnóstico de Servicios
                </h1>
                <p className="mt-1 text-sm text-darktext-secondary">
                  Estado en tiempo real de la conectividad con la API FastAPI y PostgreSQL.
                </p>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
                <div className="lg:col-span-2 space-y-6">
                  <StatusCard
                    status={connectionState}
                    healthData={healthData}
                    errorMessage={healthErrorMessage}
                    lastChecked={lastChecked}
                    onRetry={checkHealth}
                  />

                  {/* Architecture pillars */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-dark-card border border-dark-border rounded-lg p-4 hover:border-brand-emerald/40 transition-colors">
                      <div className="flex items-center gap-2 text-brand-emerald font-semibold text-xs mb-2">
                        <ShieldCheck className="w-4 h-4" />
                        <span>Gobernanza Humana</span>
                      </div>
                      <p className="text-xs text-darktext-secondary leading-relaxed">
                        Compuertas obligatorias para transformaciones materiales, selección de modelos y despliegues.
                      </p>
                    </div>
                    <div className="bg-dark-card border border-dark-border rounded-lg p-4 hover:border-brand-turquoise/40 transition-colors">
                      <div className="flex items-center gap-2 text-brand-turquoise font-semibold text-xs mb-2">
                        <GitBranch className="w-4 h-4" />
                        <span>Linaje Criptográfico</span>
                      </div>
                      <p className="text-xs text-darktext-secondary leading-relaxed">
                        Trazabilidad sellada con hashes SHA-256 canónicos desde el CSV hasta el dashboard.
                      </p>
                    </div>
                    <div className="bg-dark-card border border-dark-border rounded-lg p-4 hover:border-brand-warning/40 transition-colors">
                      <div className="flex items-center gap-2 text-brand-warning font-semibold text-xs mb-2">
                        <LayoutDashboard className="w-4 h-4" />
                        <span>Cero Fabricación</span>
                      </div>
                      <p className="text-xs text-darktext-secondary leading-relaxed">
                        Distinción transparente entre resultados medidos, estimaciones e hipótesis.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Infra panel */}
                <div className="bg-dark-secondary border border-dark-border rounded-lg p-5 text-xs space-y-4">
                  <div className="flex items-center gap-2 pb-3 border-b border-dark-border text-darktext-primary font-semibold">
                    <Database className="w-4 h-4 text-brand-emerald" />
                    <span>Infraestructura Certificada (M10)</span>
                  </div>
                  <div className="space-y-2">
                    {[
                      ['Backend API', 'FastAPI (Python)'],
                      ['Base de Datos', 'PostgreSQL 16'],
                      ['Almacén de Artefactos', 'LocalArtifactStore'],
                      ['Pruebas CI Certificadas', '87 aprobadas'],
                    ].map(([label, value]) => (
                      <div key={label} className="flex justify-between py-1.5 border-b border-dark-border/40">
                        <span className="text-darktext-secondary">{label}</span>
                        <span className="font-mono text-brand-emerald font-medium">{value}</span>
                      </div>
                    ))}
                  </div>
                  <div className="pt-1 text-[11px] text-darktext-secondary flex items-center gap-1.5">
                    <FileCode2 className="w-3.5 h-3.5" />
                    <span>React 18 + Vite + Tailwind Dark Premium</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* ── Create project modal ── */}
      <ProjectCreateModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onProjectCreated={handleProjectCreated}
      />
    </div>
  );
};

export default App;
