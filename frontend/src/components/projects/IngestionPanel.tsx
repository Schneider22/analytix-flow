import React, { FormEvent, useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  RefreshCw,
  ShieldCheck,
  Upload,
} from 'lucide-react';
import { ApiError } from '../../api/client';
import {
  ArtifactReference,
  createM2RequestIdentity,
  getIngestionFormat,
  M2IngestionResult,
  runM2,
  uploadSourceArtifact,
} from '../../api/ingestion';
import { ContextRead, DecisionRead, ProjectRead } from '../../types/projects';

interface IngestionPanelProps {
  project: ProjectRead;
  snapshots: ContextRead[];
  decisions: DecisionRead[];
}

function latestSnapshot(snapshots: ContextRead[]): ContextRead | null {
  return snapshots.reduce<ContextRead | null>(
    (latest, snapshot) => (!latest || snapshot.version > latest.version ? snapshot : latest),
    null,
  );
}

function selectedAlternative(decisions: DecisionRead[]): DecisionRead | null {
  return decisions.find(
    (decision) =>
      decision.decision_type === 'select_alternative' &&
      decision.status === 'decided' &&
      Boolean(decision.selected_option),
  ) ?? null;
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return 'No se pudo completar la ingesta.';
}

function displayError(error: Record<string, unknown>): string {
  if (typeof error.message === 'string') return error.message;
  return JSON.stringify(error) || 'Error no especificado';
}

export const IngestionPanel: React.FC<IngestionPanelProps> = ({ project, snapshots, decisions }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [sourceArtifact, setSourceArtifact] = useState<ArtifactReference | null>(null);
  const [result, setResult] = useState<M2IngestionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [requestIdentity, setRequestIdentity] = useState(createM2RequestIdentity);

  const contextSnapshot = useMemo(() => latestSnapshot(snapshots), [snapshots]);
  const alternativeDecision = useMemo(() => selectedAlternative(decisions), [decisions]);
  const isArchived = project.status === 'archived' || Boolean(project.archived_at);
  const hasPrerequisites = Boolean(contextSnapshot && alternativeDecision?.selected_option);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
    setSourceArtifact(null);
    setResult(null);
    setError(null);
    setRequestIdentity(createM2RequestIdentity());
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);

    if (isArchived) {
      setError('Los proyectos archivados están disponibles solo en modo de lectura.');
      return;
    }
    if (!contextSnapshot) {
      setError('Se necesita una instantánea de contexto para ejecutar M2.');
      return;
    }
    if (!alternativeDecision?.selected_option) {
      setError('Se necesita una decisión select_alternative decidida para ejecutar M2.');
      return;
    }
    if (!selectedFile && !sourceArtifact) {
      setError('Selecciona un archivo CSV, XLSX o XLS antes de ejecutar M2.');
      return;
    }

    const format = selectedFile ? getIngestionFormat(selectedFile.name) : null;
    if (selectedFile && !format) {
      setError('Formato no soportado. Selecciona un archivo CSV, XLSX o XLS.');
      return;
    }

    setIsSubmitting(true);
    try {
      let artifact = sourceArtifact;
      if (!artifact && selectedFile && format) {
        artifact = await uploadSourceArtifact(project.id, selectedFile, format);
        setSourceArtifact(artifact);
      }

      if (!artifact) {
        throw new Error('No se pudo registrar el artefacto fuente.');
      }

      const ingestionResult = await runM2(project.id, {
        contextSnapshotId: contextSnapshot.id,
        selectedAlternativeId: alternativeDecision.selected_option,
        sourceArtifact: artifact,
        format: format ?? 'csv',
        identity: requestIdentity,
      });
      setResult(ingestionResult);
    } catch (submissionError: unknown) {
      setError(errorMessage(submissionError));
    } finally {
      setIsSubmitting(false);
    }
  };

  const profile = result?.module_output?.profile_report;
  const bronze = result?.module_output?.bronze_dataset;
  const issues = result?.module_output?.issues ?? [];
  const warnings = result?.warnings ?? [];
  const errors = result?.errors ?? [];

  return (
    <div className="space-y-5" data-testid="ingestion-panel">
      <div className="bg-dark-secondary border border-dark-border rounded-xl p-5 space-y-3">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-brand-turquoise font-semibold text-sm">
              <Database className="w-4 h-4" />
              <h2>Ingesta Bronze y perfilado inicial</h2>
            </div>
            <p className="text-xs text-darktext-secondary mt-1">
              Registra la fuente original y ejecuta el perfilado determinista de M2 sin modificar sus bytes.
            </p>
          </div>
          <span className="text-[10px] font-mono text-brand-emerald border border-brand-emerald/30 bg-emerald-950/30 rounded px-2 py-1">
            M2 · v1.0
          </span>
        </div>

        {isArchived ? (
          <div className="flex items-start gap-2 rounded-lg border border-amber-700/50 bg-amber-950/30 p-3 text-xs text-amber-100">
            <ShieldCheck className="w-4 h-4 text-brand-warning flex-shrink-0 mt-0.5" />
            <span>Proyecto archivado: la consulta histórica está habilitada, pero la carga y ejecución están bloqueadas.</span>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div className={`rounded-lg border p-3 ${contextSnapshot ? 'border-brand-emerald/30 bg-emerald-950/20' : 'border-amber-700/50 bg-amber-950/20'}`}>
              <span className="font-semibold text-darktext-primary block">Snapshot de contexto</span>
              <span className="text-darktext-secondary">
                {contextSnapshot ? `Versión ${contextSnapshot.version} · ${contextSnapshot.id}` : 'Falta una instantánea de contexto.'}
              </span>
            </div>
            <div className={`rounded-lg border p-3 ${alternativeDecision?.selected_option ? 'border-brand-emerald/30 bg-emerald-950/20' : 'border-amber-700/50 bg-amber-950/20'}`}>
              <span className="font-semibold text-darktext-primary block">Alternativa aprobada</span>
              <span className="text-darktext-secondary">
                {alternativeDecision?.selected_option ?? 'Falta una decisión select_alternative decidida.'}
              </span>
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3 pt-2">
          <div>
            <label htmlFor="ingestion-file" className="block text-xs font-semibold text-darktext-primary mb-1.5">
              Archivo de datos
            </label>
            <div className="flex flex-col sm:flex-row gap-2">
              <input
                id="ingestion-file"
                type="file"
                accept=".csv,.xlsx,.xls,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                onChange={handleFileChange}
                disabled={isArchived || isSubmitting}
                className="block w-full text-xs text-darktext-secondary file:mr-3 file:rounded-lg file:border file:border-dark-border file:bg-dark-elevated file:px-3 file:py-2 file:text-xs file:font-semibold file:text-brand-turquoise hover:file:bg-dark-border disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={isArchived || isSubmitting || !hasPrerequisites || (!selectedFile && !sourceArtifact)}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-brand-emerald px-4 py-2 text-xs font-bold text-dark-primary transition-colors hover:bg-brand-emeraldHover disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isSubmitting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                {isSubmitting ? 'Procesando…' : sourceArtifact ? 'Reintentar M2' : 'Cargar y perfilar'}
              </button>
            </div>
            <p className="text-[11px] text-darktext-secondary mt-1">
              CSV es el flujo principal de la demo; también se aceptan XLSX y XLS con las opciones predeterminadas del contrato.
            </p>
          </div>
        </form>

        {error && (
          <div role="alert" className="flex items-start gap-2 rounded-lg border border-brand-error/40 bg-rose-950/30 p-3 text-xs text-rose-200">
            <AlertTriangle className="w-4 h-4 text-brand-error flex-shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {sourceArtifact && (
          <div data-testid="source-artifact-reference" className="rounded-lg border border-dark-border bg-dark-elevated p-3 text-[11px] space-y-1">
            <span className="font-semibold text-darktext-primary">Fuente preservada</span>
            <div className="font-mono text-darktext-secondary break-all">
              {sourceArtifact.artifact_id} · {sourceArtifact.artifact_version} · {sourceArtifact.content_hash}
            </div>
          </div>
        )}
      </div>

      {result && (
        <section data-testid="ingestion-result" className="bg-dark-card border border-dark-border rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between gap-3 border-b border-dark-border pb-3">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-brand-emerald" />
              <h3 className="text-sm font-semibold text-darktext-primary">Resultado real de perfilado Bronze</h3>
            </div>
            <span className="text-[11px] font-mono text-brand-emerald">{result.status}</span>
          </div>

          {profile && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
              {profile.row_count !== undefined && <div className="rounded-lg bg-dark-elevated border border-dark-border p-3"><span className="block text-darktext-secondary">Filas</span><strong className="text-darktext-primary">{profile.row_count}</strong></div>}
              {profile.column_count !== undefined && <div className="rounded-lg bg-dark-elevated border border-dark-border p-3"><span className="block text-darktext-secondary">Columnas</span><strong className="text-darktext-primary">{profile.column_count}</strong></div>}
              {profile.structures && <div className="rounded-lg bg-dark-elevated border border-dark-border p-3"><span className="block text-darktext-secondary">Estructuras</span><strong className="text-darktext-primary">{profile.structures.join(', ')}</strong></div>}
              {profile.potential_identifiers && <div className="rounded-lg bg-dark-elevated border border-dark-border p-3"><span className="block text-darktext-secondary">Identificadores</span><strong className="text-darktext-primary">{profile.potential_identifiers.length}</strong></div>}
            </div>
          )}

          {profile?.columns && profile.columns.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="text-left text-darktext-secondary border-b border-dark-border">
                  <tr><th className="py-2 pr-3">Columna</th><th className="py-2 pr-3">Tipo</th><th className="py-2 pr-3">Nulos</th><th className="py-2">Únicos</th></tr>
                </thead>
                <tbody>
                  {profile.columns.map((column) => (
                    <tr key={column.name} className="border-b border-dark-border/50">
                      <td className="py-2 pr-3 text-darktext-primary font-medium">{column.name}</td>
                      <td className="py-2 pr-3 text-brand-turquoise font-mono">{column.dtype}</td>
                      <td className="py-2 pr-3 text-darktext-secondary">{column.missing_count}</td>
                      <td className="py-2 text-darktext-secondary">{column.unique_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {(warnings.length > 0 || issues.length > 0) && (
            <div className="space-y-2">
              <h4 className="text-xs font-semibold text-brand-warning">Advertencias y observaciones</h4>
              {warnings.map((warning) => <p key={warning} className="text-xs text-darktext-secondary">{warning}</p>)}
              {issues.map((issue, index) => <p key={issue.issue_id ?? `${issue.description}-${index}`} className="text-xs text-darktext-secondary">{issue.severity ? `[${issue.severity}] ` : ''}{issue.description}</p>)}
            </div>
          )}

          {errors.length > 0 && (
            <div className="space-y-2 rounded-lg border border-brand-error/30 bg-rose-950/20 p-3">
              <h4 className="text-xs font-semibold text-brand-error">Errores del perfilado</h4>
              {errors.map((item, index) => <p key={index} className="text-xs text-rose-200">{displayError(item)}</p>)}
            </div>
          )}

          {bronze && (
            <div data-testid="bronze-reference" className="rounded-lg border border-brand-emerald/30 bg-emerald-950/20 p-3 text-xs">
              <span className="font-semibold text-brand-emerald">Artefacto Bronze</span>
              <div className="mt-1 font-mono text-darktext-secondary break-all">
                {bronze.artifact_id} · {bronze.artifact_version} · {bronze.content_hash}
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
};
