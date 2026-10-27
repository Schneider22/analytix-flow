import React, { useState, useEffect } from 'react';
import { ContextCreate, ContextPayload, ContextRead, ProjectRead } from '../../types/projects';
import { createContextSnapshot } from '../../api/context';
import { StringListInput } from '../common/StringListInput';
import { X, RefreshCw, AlertTriangle, Check, History } from 'lucide-react';
import { ApiError } from '../../api/client';

interface ContextCreateModalProps {
  isOpen: boolean;
  onClose: () => void;
  project: ProjectRead;
  latestSnapshot: ContextRead | null;
  onSnapshotCreated: (snapshot: ContextRead) => void;
}

export const ContextCreateModal: React.FC<ContextCreateModalProps> = ({
  isOpen,
  onClose,
  project,
  latestSnapshot,
  onSnapshotCreated,
}) => {
  const [companyName, setCompanyName] = useState('');
  const [companyDescription, setCompanyDescription] = useState('');
  const [businessNeed, setBusinessNeed] = useState('');
  const [expectedObjective, setExpectedObjective] = useState('');
  const [assumptions, setAssumptions] = useState<string[]>([]);
  const [successCriteria, setSuccessCriteria] = useState<string[]>([]);
  const [businessRules, setBusinessRules] = useState<string[]>([]);
  const [constraints, setConstraints] = useState<string[]>([]);
  const [createdBy, setCreatedBy] = useState('');

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Preload data from latest snapshot if present, else from project base fields
  useEffect(() => {
    if (latestSnapshot) {
      const ctx = latestSnapshot.context;
      setCompanyName(ctx.company_name);
      setCompanyDescription(ctx.company_description);
      setBusinessNeed(ctx.business_need);
      setExpectedObjective(ctx.expected_objective);
      setAssumptions(ctx.assumptions ?? []);
      setSuccessCriteria(ctx.success_criteria ?? []);
      setBusinessRules(ctx.business_rules ?? []);
      setConstraints(ctx.constraints ?? []);
      setCreatedBy(latestSnapshot.created_by || project.owner_id || '');
    } else {
      setCompanyName(project.company_name);
      setCompanyDescription(project.company_description);
      setBusinessNeed(project.business_need);
      setExpectedObjective(project.expected_objective);
      setAssumptions([]);
      setSuccessCriteria(project.success_criteria ?? []);
      setBusinessRules(project.business_rules ?? []);
      setConstraints(project.constraints ?? []);
      setCreatedBy(project.owner_id || '');
    }
  }, [latestSnapshot, project]);

  if (!isOpen) return null;

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    if (!companyName.trim()) {
      errors.companyName = 'El nombre de la empresa es obligatorio';
    }
    if (!companyDescription.trim()) {
      errors.companyDescription = 'La descripción es obligatoria';
    }
    if (!businessNeed.trim()) {
      errors.businessNeed = 'La necesidad de negocio es obligatoria';
    }
    if (!expectedObjective.trim()) {
      errors.expectedObjective = 'El objetivo esperado es obligatorio';
    }
    if (successCriteria.length === 0) {
      errors.successCriteria = 'Debes definir al menos un criterio de éxito';
    }
    if (!createdBy.trim()) {
      errors.createdBy = 'El campo created_by (autor) es obligatorio';
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);

    const payloadContext: ContextPayload = {
      company_name: companyName,
      company_description: companyDescription,
      business_need: businessNeed,
      expected_objective: expectedObjective,
      business_rules: businessRules,
      constraints: constraints,
      assumptions: assumptions,
      success_criteria: successCriteria,
    };

    const payload: ContextCreate = {
      context: payloadContext,
      created_by: createdBy,
    };

    try {
      const created = await createContextSnapshot(project.id, payload);
      onSnapshotCreated(created);
      onClose();
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setSubmitError(err.message);
      } else if (err instanceof Error) {
        setSubmitError(err.message);
      } else {
        setSubmitError('Error inesperado al registrar la instantánea de contexto');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const nextVersion = latestSnapshot ? latestSnapshot.version + 1 : 1;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      className="fixed inset-0 z-50 overflow-y-auto bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
    >
      <div className="bg-dark-card rounded-2xl shadow-2xl border border-dark-border max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Cabecera del Modal */}
        <div className="px-6 py-4 border-b border-dark-border flex items-center justify-between bg-dark-secondary">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 bg-emerald-950/80 border border-emerald-500/40 text-brand-emerald rounded-lg">
              <History className="w-5 h-5" />
            </div>
            <div>
              <h3 id="modal-title" className="text-base font-bold text-darktext-primary">
                Registrar Nueva Instantánea de Contexto
              </h3>
              <p className="text-xs text-darktext-secondary">
                Versión a registrar: <span className="font-semibold text-brand-emerald">v{nextVersion}</span>{' '}
                {latestSnapshot && `(Predecesor: v${latestSnapshot.version})`}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="text-darktext-secondary hover:text-darktext-primary p-1.5 rounded-lg hover:bg-dark-elevated transition-colors"
            aria-label="Cerrar modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Cuerpo del Formulario */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-4 text-xs">
          {submitError && (
            <div className="p-3 bg-rose-950/30 border border-brand-error/40 rounded-lg text-darktext-primary flex items-start space-x-2">
              <AlertTriangle className="w-4 h-4 text-brand-error flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-brand-error">Error al registrar la instantánea</p>
                <p className="text-[11px] font-mono mt-0.5 text-rose-300">{submitError}</p>
              </div>
            </div>
          )}

          {/* Autor de la Instantánea */}
          <div className="bg-dark-elevated p-3.5 rounded-xl border border-dark-border">
            <label htmlFor="context-created-by" className="block font-semibold text-darktext-primary mb-1">
              Autor / Responsable del Contexto (created_by) <span className="text-brand-error">*</span>
            </label>
            <input
              id="context-created-by"
              type="text"
              value={createdBy}
              onChange={(e) => setCreatedBy(e.target.value)}
              placeholder="Ej. lead-data-scientist"
              maxLength={128}
              className="w-full text-xs rounded-lg border border-dark-border bg-dark-card px-3 py-2 text-darktext-primary placeholder-darktext-secondary/50 focus:outline-none focus:ring-1 focus:ring-brand-emerald focus:border-brand-emerald transition-colors"
            />
            {fieldErrors.createdBy && (
              <p className="text-[11px] text-brand-error mt-1">{fieldErrors.createdBy}</p>
            )}
            <p className="text-[11px] text-darktext-secondary mt-1">
              Este identificador se estampará de forma inmutable en el registro de auditoría y en la cadena de linaje.
            </p>
          </div>

          {/* Suposiciones / Hipótesis (Assumptions) */}
          <div className="pt-2 border-t border-dark-border/60">
            <StringListInput
              id="context-assumptions-input"
              label="Suposiciones e Hipótesis del Problema (Assumptions)"
              description="Hipótesis técnicas o de negocio que condicionan las decisiones analíticas."
              placeholder="Ej. Se asume que no hay estacionalidad mensual en churn"
              items={assumptions}
              onChange={setAssumptions}
            />
          </div>

          {/* Criterios de Éxito */}
          <div className="pt-2 border-t border-dark-border/60">
            <StringListInput
              id="context-success-criteria-input"
              label="Criterios de Éxito Medibles"
              description="Métricas mínimas requeridas para aceptar la solución analítica."
              placeholder="Ej. Precision >= 0.70"
              items={successCriteria}
              onChange={setSuccessCriteria}
              required
              minItems={1}
              errorMessage={fieldErrors.successCriteria}
            />
          </div>

          {/* Reglas de Negocio */}
          <div className="pt-2 border-t border-dark-border/60">
            <StringListInput
              id="context-business-rules-input"
              label="Reglas de Negocio Actualizadas"
              description="Políticas operativas aplicables a los datos y modelos."
              placeholder="Ej. Tratar cuentas inactivas como churn voluntario"
              items={businessRules}
              onChange={setBusinessRules}
            />
          </div>

          {/* Restricciones */}
          <div className="pt-2 border-t border-dark-border/60">
            <StringListInput
              id="context-constraints-input"
              label="Restricciones Técnicas"
              description="Condiciones de hardware, privacidad o entorno de despliegue."
              placeholder="Ej. Tiempo de inferencia inferior a 50ms"
              items={constraints}
              onChange={setConstraints}
            />
          </div>

          {/* Ficha Base de Contexto (Campos de texto) */}
          <div className="pt-2 border-t border-dark-border/60 space-y-3">
            <div>
              <label htmlFor="context-company-name" className="block font-semibold text-darktext-primary mb-1">
                Nombre de la Empresa <span className="text-brand-error">*</span>
              </label>
              <input
                id="context-company-name"
                type="text"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                className="w-full text-xs rounded-lg border border-dark-border bg-dark-elevated px-3 py-2 text-darktext-primary placeholder-darktext-secondary/50 focus:outline-none focus:ring-1 focus:ring-brand-emerald focus:border-brand-emerald transition-colors"
              />
              {fieldErrors.companyName && (
                <p className="text-[11px] text-brand-error mt-1">{fieldErrors.companyName}</p>
              )}
            </div>

            <div>
              <label htmlFor="context-business-need" className="block font-semibold text-darktext-primary mb-1">
                Necesidad o Problema de Negocio <span className="text-brand-error">*</span>
              </label>
              <textarea
                id="context-business-need"
                rows={2}
                value={businessNeed}
                onChange={(e) => setBusinessNeed(e.target.value)}
                className="w-full text-xs rounded-lg border border-dark-border bg-dark-elevated px-3 py-2 text-darktext-primary placeholder-darktext-secondary/50 focus:outline-none focus:ring-1 focus:ring-brand-emerald focus:border-brand-emerald transition-colors"
              />
              {fieldErrors.businessNeed && (
                <p className="text-[11px] text-brand-error mt-1">{fieldErrors.businessNeed}</p>
              )}
            </div>

            <div>
              <label htmlFor="context-expected-objective" className="block font-semibold text-darktext-primary mb-1">
                Objetivo Esperado <span className="text-brand-error">*</span>
              </label>
              <textarea
                id="context-expected-objective"
                rows={2}
                value={expectedObjective}
                onChange={(e) => setExpectedObjective(e.target.value)}
                className="w-full text-xs rounded-lg border border-dark-border bg-dark-elevated px-3 py-2 text-darktext-primary placeholder-darktext-secondary/50 focus:outline-none focus:ring-1 focus:ring-brand-emerald focus:border-brand-emerald transition-colors"
              />
              {fieldErrors.expectedObjective && (
                <p className="text-[11px] text-brand-error mt-1">{fieldErrors.expectedObjective}</p>
              )}
            </div>

            <div>
              <label htmlFor="context-company-description" className="block font-semibold text-darktext-primary mb-1">
                Descripción de la Empresa <span className="text-brand-error">*</span>
              </label>
              <textarea
                id="context-company-description"
                rows={2}
                value={companyDescription}
                onChange={(e) => setCompanyDescription(e.target.value)}
                className="w-full text-xs rounded-lg border border-dark-border bg-dark-elevated px-3 py-2 text-darktext-primary placeholder-darktext-secondary/50 focus:outline-none focus:ring-1 focus:ring-brand-emerald focus:border-brand-emerald transition-colors"
              />
              {fieldErrors.companyDescription && (
                <p className="text-[11px] text-brand-error mt-1">{fieldErrors.companyDescription}</p>
              )}
            </div>
          </div>

          {/* Pie del Formulario */}
          <div className="pt-4 border-t border-dark-border flex items-center justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 text-xs font-semibold rounded-lg text-darktext-secondary bg-dark-elevated border border-dark-border hover:text-darktext-primary hover:bg-dark-border disabled:opacity-50 transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="inline-flex items-center space-x-1.5 px-4 py-2 text-xs font-bold rounded-lg text-dark-primary bg-brand-emerald hover:bg-brand-emeraldHover disabled:opacity-50 transition-colors shadow-sm shadow-emerald-950/40"
            >
              {isSubmitting ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Registrando v{nextVersion}...</span>
                </>
              ) : (
                <>
                  <Check className="w-3.5 h-3.5" />
                  <span>Registrar Instantánea v{nextVersion}</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
