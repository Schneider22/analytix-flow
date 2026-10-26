import React, { useState } from 'react';
import { ProjectCreate, ProjectRead } from '../../types/projects';
import { createProject } from '../../api/projects';
import { StringListInput } from '../common/StringListInput';
import { X, RefreshCw, AlertTriangle, Check } from 'lucide-react';
import { ApiError } from '../../api/client';

interface ProjectCreateModalProps {
  isOpen: boolean;
  onClose: () => void;
  onProjectCreated: (project: ProjectRead) => void;
}

export const ProjectCreateModal: React.FC<ProjectCreateModalProps> = ({
  isOpen,
  onClose,
  onProjectCreated,
}) => {
  const [companyName, setCompanyName] = useState('');
  const [companyDescription, setCompanyDescription] = useState('');
  const [businessNeed, setBusinessNeed] = useState('');
  const [expectedObjective, setExpectedObjective] = useState('');
  const [successCriteria, setSuccessCriteria] = useState<string[]>([]);
  const [businessRules, setBusinessRules] = useState<string[]>([]);
  const [constraints, setConstraints] = useState<string[]>([]);
  const [ownerId, setOwnerId] = useState('');
  const [organizationId, setOrganizationId] = useState('');

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    if (!companyName.trim()) {
      errors.companyName = 'El nombre de la empresa es obligatorio (mínimo 1 carácter)';
    } else if (companyName.length > 255) {
      errors.companyName = 'El nombre no puede exceder 255 caracteres';
    }

    if (!companyDescription.trim()) {
      errors.companyDescription = 'La descripción de la empresa es obligatoria';
    }

    if (!businessNeed.trim()) {
      errors.businessNeed = 'La necesidad de negocio es obligatoria';
    }

    if (!expectedObjective.trim()) {
      errors.expectedObjective = 'El objetivo esperado es obligatorio';
    }

    if (successCriteria.length === 0) {
      errors.successCriteria = 'Debes definir al menos un criterio de éxito verificable';
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

    const payload: ProjectCreate = {
      company_name: companyName,
      company_description: companyDescription,
      business_need: businessNeed,
      expected_objective: expectedObjective,
      success_criteria: successCriteria,
      business_rules: businessRules,
      constraints: constraints,
      owner_id: ownerId.trim() || null,
      organization_id: organizationId.trim() || null,
    };

    try {
      const created = await createProject(payload);
      onProjectCreated(created);
      onClose();
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setSubmitError(err.message);
      } else if (err instanceof Error) {
        setSubmitError(err.message);
      } else {
        setSubmitError('Error inesperado al crear el proyecto');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4"
    >
      <div className="bg-white rounded-2xl shadow-xl border border-slate-200 max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Cabecera del Modal */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div>
            <h3 id="modal-title" className="text-base font-bold text-slate-900">
              Registrar Nuevo Proyecto Analítico
            </h3>
            <p className="text-xs text-slate-500">
              Fase M1: Entendimiento del Negocio y Definición del Problema
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-200 transition-colors"
            aria-label="Cerrar modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Cuerpo del Formulario */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-4 text-xs">
          {submitError && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-800 flex items-start space-x-2">
              <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Error al registrar el proyecto</p>
                <p className="text-[11px] font-mono mt-0.5">{submitError}</p>
              </div>
            </div>
          )}

          {/* Empresa, Responsable y Organización */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label htmlFor="company-name" className="block font-semibold text-slate-700 mb-1">
                Nombre de la Empresa <span className="text-rose-500">*</span>
              </label>
              <input
                id="company-name"
                type="text"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="Ej. TelcoGlobal Synthetic Services"
                maxLength={255}
                className="w-full text-xs rounded-lg border border-slate-300 px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
              {fieldErrors.companyName && (
                <p className="text-[11px] text-rose-600 mt-1">{fieldErrors.companyName}</p>
              )}
            </div>

            <div>
              <label htmlFor="owner-id" className="block font-semibold text-slate-700 mb-1">
                Responsable (Owner ID)
              </label>
              <input
                id="owner-id"
                type="text"
                value={ownerId}
                onChange={(e) => setOwnerId(e.target.value)}
                placeholder="Ej. lead-data-scientist"
                maxLength={128}
                className="w-full text-xs rounded-lg border border-slate-300 px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>

            <div>
              <label htmlFor="organization-id" className="block font-semibold text-slate-700 mb-1">
                Organización (Org ID)
              </label>
              <input
                id="organization-id"
                type="text"
                value={organizationId}
                onChange={(e) => setOrganizationId(e.target.value)}
                placeholder="Ej. org-synthetic-01"
                maxLength={128}
                className="w-full text-xs rounded-lg border border-slate-300 px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
            </div>
          </div>

          {/* Descripción de la Empresa */}
          <div>
            <label htmlFor="company-description" className="block font-semibold text-slate-700 mb-1">
              Descripción de la Empresa <span className="text-rose-500">*</span>
            </label>
            <textarea
              id="company-description"
              rows={2}
              value={companyDescription}
              onChange={(e) => setCompanyDescription(e.target.value)}
              placeholder="Actividad principal, industria, modelo operativo..."
              maxLength={10000}
              className="w-full text-xs rounded-lg border border-slate-300 px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
            {fieldErrors.companyDescription && (
              <p className="text-[11px] text-rose-600 mt-0.5">{fieldErrors.companyDescription}</p>
            )}
          </div>

          {/* Necesidad de Negocio */}
          <div>
            <label htmlFor="business-need" className="block font-semibold text-slate-700 mb-1">
              Necesidad o Problema de Negocio <span className="text-rose-500">*</span>
            </label>
            <textarea
              id="business-need"
              rows={2}
              value={businessNeed}
              onChange={(e) => setBusinessNeed(e.target.value)}
              placeholder="¿Qué problema operativo o estratégico se busca resolver?"
              maxLength={10000}
              className="w-full text-xs rounded-lg border border-slate-300 px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
            {fieldErrors.businessNeed && (
              <p className="text-[11px] text-rose-600 mt-0.5">{fieldErrors.businessNeed}</p>
            )}
          </div>

          {/* Objetivo Esperado */}
          <div>
            <label htmlFor="expected-objective" className="block font-semibold text-slate-700 mb-1">
              Objetivo Esperado <span className="text-rose-500">*</span>
            </label>
            <textarea
              id="expected-objective"
              rows={2}
              value={expectedObjective}
              onChange={(e) => setExpectedObjective(e.target.value)}
              placeholder="¿Cuál es el resultado analítico esperado para orientar la toma de decisiones?"
              maxLength={10000}
              className="w-full text-xs rounded-lg border border-slate-300 px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
            {fieldErrors.expectedObjective && (
              <p className="text-[11px] text-rose-600 mt-0.5">{fieldErrors.expectedObjective}</p>
            )}
          </div>

          {/* Criterios de Éxito (Obligatorio, min 1) */}
          <div className="pt-2 border-t border-slate-100">
            <StringListInput
              id="success-criteria-input"
              label="Criterios de Éxito Medibles"
              description="Metas medibles para evaluar el éxito de la solución (ej. F1-score >= 0.60, linaje unbroken)."
              placeholder="Ej. Holdout F1-score >= 0.60"
              items={successCriteria}
              onChange={setSuccessCriteria}
              required
              minItems={1}
              errorMessage={fieldErrors.successCriteria}
            />
          </div>

          {/* Reglas de Negocio (Opcional) */}
          <div className="pt-2 border-t border-slate-100">
            <StringListInput
              id="business-rules-input"
              label="Reglas de Negocio"
              description="Políticas organizacionales o de gobernanza (ej. Aislar registros de suscriptores)."
              placeholder="Ej. Aislar registros de suscriptores"
              items={businessRules}
              onChange={setBusinessRules}
            />
          </div>

          {/* Restricciones (Opcional) */}
          <div className="pt-2 border-t border-slate-100">
            <StringListInput
              id="constraints-input"
              label="Restricciones Técnicas u Operativas"
              description="Límites del proyecto (ej. Ejecución estrictamente local, sin nube)."
              placeholder="Ej. Ejecución estrictamente local"
              items={constraints}
              onChange={setConstraints}
            />
          </div>

          {/* Pie y Botones */}
          <div className="pt-4 border-t border-slate-200 flex items-center justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="px-4 py-2 text-xs font-semibold rounded-lg text-slate-700 bg-slate-100 hover:bg-slate-200 disabled:opacity-50 transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="inline-flex items-center space-x-1.5 px-4 py-2 text-xs font-semibold rounded-lg text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 transition-colors shadow-sm"
            >
              {isSubmitting ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Registrando...</span>
                </>
              ) : (
                <>
                  <Check className="w-3.5 h-3.5" />
                  <span>Crear Proyecto</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
