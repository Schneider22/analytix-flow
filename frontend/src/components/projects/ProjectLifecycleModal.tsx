import React, { useEffect, useState } from 'react';
import { AlertTriangle, Archive, RotateCcw, X } from 'lucide-react';
import { ProjectRead } from '../../types/projects';

export type ProjectLifecycleAction = 'archive' | 'restore';

interface ProjectLifecycleModalProps {
  isOpen: boolean;
  action: ProjectLifecycleAction;
  project: ProjectRead;
  isSubmitting: boolean;
  errorMessage: string | null;
  onClose: () => void;
  onSubmit: (payload: { actor_id: string; reason?: string }) => void;
}

export const ProjectLifecycleModal: React.FC<ProjectLifecycleModalProps> = ({
  isOpen,
  action,
  project,
  isSubmitting,
  errorMessage,
  onClose,
  onSubmit,
}) => {
  const [actorId, setActorId] = useState(project.owner_id ?? '');
  const [reason, setReason] = useState('');

  useEffect(() => {
    if (isOpen) {
      setActorId(project.owner_id ?? '');
      setReason('');
    }
  }, [isOpen, project.owner_id]);

  if (!isOpen) return null;

  const isArchive = action === 'archive';
  const title = isArchive ? 'Archivar proyecto' : 'Restaurar proyecto';
  const submitLabel = isArchive ? 'Archivar proyecto' : 'Restaurar proyecto';

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit({ actor_id: actorId.trim(), ...(isArchive || reason.trim() ? { reason: reason.trim() } : {}) });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="project-lifecycle-title">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} aria-hidden="true" />
      <form
        onSubmit={handleSubmit}
        className="relative w-full max-w-md space-y-5 rounded-xl border border-dark-border bg-dark-secondary p-6 shadow-2xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className={`mt-0.5 rounded-lg p-2 ${isArchive ? 'bg-amber-950/70 text-brand-warning' : 'bg-emerald-950/70 text-brand-emerald'}`}>
              {isArchive ? <Archive className="h-5 w-5" /> : <RotateCcw className="h-5 w-5" />}
            </div>
            <div>
              <h2 id="project-lifecycle-title" className="text-base font-bold text-darktext-primary">{title}</h2>
              <p className="mt-1 text-xs text-darktext-secondary">{project.company_name}</p>
            </div>
          </div>
          <button type="button" onClick={onClose} disabled={isSubmitting} aria-label="Cerrar" className="rounded-md p-1 text-darktext-secondary hover:bg-dark-elevated hover:text-darktext-primary">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="rounded-lg border border-dark-border bg-dark-card p-3 text-xs text-darktext-secondary">
          <div className="flex items-start gap-2">
            <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0 text-brand-warning" />
            <p>
              {isArchive
                ? 'El proyecto se conservará junto con sus relaciones históricas y quedará en modo solo lectura.'
                : 'El proyecto volverá a su estado anterior y recuperará las operaciones mutantes permitidas.'}
            </p>
          </div>
        </div>

        <label className="block text-xs text-darktext-secondary">
          Actor responsable
          <input
            value={actorId}
            onChange={(event) => setActorId(event.target.value)}
            required
            maxLength={128}
            className="mt-1 w-full rounded-lg border border-dark-border bg-dark-elevated px-3 py-2 text-xs text-darktext-primary outline-none focus:border-brand-emerald focus:ring-1 focus:ring-brand-emerald"
            placeholder="usuario o servicio"
          />
        </label>

        <label className="block text-xs text-darktext-secondary">
          Motivo {isArchive ? '(obligatorio)' : '(opcional)'}
          <textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            required={isArchive}
            maxLength={10000}
            rows={3}
            className="mt-1 w-full resize-none rounded-lg border border-dark-border bg-dark-elevated px-3 py-2 text-xs text-darktext-primary outline-none focus:border-brand-emerald focus:ring-1 focus:ring-brand-emerald"
            placeholder={isArchive ? 'Documenta por qué se archiva el proyecto' : 'Opcional'}
          />
        </label>

        {errorMessage && <p className="text-xs text-brand-error">{errorMessage}</p>}

        <div className="flex justify-end gap-2 border-t border-dark-border pt-4">
          <button type="button" onClick={onClose} disabled={isSubmitting} className="rounded-lg border border-dark-border bg-dark-elevated px-3 py-2 text-xs font-semibold text-darktext-secondary hover:text-darktext-primary">
            Cancelar
          </button>
          <button type="submit" disabled={isSubmitting || !actorId.trim() || (isArchive && !reason.trim())} className={`rounded-lg px-3 py-2 text-xs font-bold text-dark-primary disabled:cursor-not-allowed disabled:opacity-50 ${isArchive ? 'bg-brand-warning hover:bg-amber-300' : 'bg-brand-emerald hover:bg-brand-emeraldHover'}`}>
            {isSubmitting ? 'Guardando…' : submitLabel}
          </button>
        </div>
      </form>
    </div>
  );
};
