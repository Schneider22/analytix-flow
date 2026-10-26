import React, { useState } from 'react';
import { DecisionCreate, DecisionRead, DecisionStatus } from '../../types/projects';
import { createDecision } from '../../api/decisions';
import { StringListInput } from '../common/StringListInput';
import { X, RefreshCw, AlertTriangle, Check, Sparkles, Scale } from 'lucide-react';
import { ApiError } from '../../api/client';

interface DecisionCreateModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  defaultDecidedBy?: string;
  onDecisionCreated: (decision: DecisionRead) => void;
}

export const DecisionCreateModal: React.FC<DecisionCreateModalProps> = ({
  isOpen,
  onClose,
  projectId,
  defaultDecidedBy = '',
  onDecisionCreated,
}) => {
  const [decisionType, setDecisionType] = useState('select_alternative');
  const [question, setQuestion] = useState('');
  const [options, setOptions] = useState<string[]>([]);
  const [selectedOption, setSelectedOption] = useState('');
  const [rationale, setRationale] = useState('');
  const [status, setStatus] = useState<DecisionStatus>('pending');
  const [decidedBy, setDecidedBy] = useState(defaultDecidedBy);

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleLoadTemplate = () => {
    setDecisionType('select_alternative');
    setQuestion('¿Qué estrategia de modelado analítico debe implementarse para este problema?');
    const templateOptions = [
      'supervised_tabular_classification',
      'heuristic_business_rule_engine',
      'unsupervised_anomaly_clustering',
    ];
    setOptions(templateOptions);
    setSelectedOption(templateOptions[0]);
    setRationale(
      'Se evalúa la formulación óptima considerando datos tabulares estructurados y métricas de negocio.'
    );
    setStatus('decided');
    if (!decidedBy.trim() && defaultDecidedBy) {
      setDecidedBy(defaultDecidedBy);
    }
  };

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {};

    if (!decisionType.trim()) {
      errors.decisionType = 'El tipo de decisión es obligatorio';
    }
    if (!question.trim()) {
      errors.question = 'La pregunta de decisión es obligatoria';
    }
    if (options.length === 0) {
      errors.options = 'Debes añadir al menos una opción a evaluar';
    }

    if (status === 'decided') {
      if (!selectedOption || !options.includes(selectedOption)) {
        errors.selectedOption =
          'Cuando el estado es "decided", debes seleccionar una opción válida de la lista';
      }
      if (!decidedBy.trim()) {
        errors.decidedBy =
          'Cuando el estado es "decided", el campo "decided_by" (responsable) es obligatorio';
      }
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

    const payload: DecisionCreate = {
      decision_type: decisionType.trim(),
      question: question.trim(),
      options: options,
      selected_option: status === 'decided' ? selectedOption : null,
      rationale: rationale.trim() ? rationale.trim() : null,
      status: status,
      evidence_artifact_ids: [],
      evidence_artifact_refs: [],
      decided_by: status === 'decided' ? decidedBy.trim() : null,
    };

    try {
      const created = await createDecision(projectId, payload);
      onDecisionCreated(created);
      onClose();
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setSubmitError(err.message);
      } else if (err instanceof Error) {
        setSubmitError(err.message);
      } else {
        setSubmitError('Error inesperado al registrar la decisión de negocio');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="decision-modal-title"
      className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4"
    >
      <div className="bg-white rounded-2xl shadow-xl border border-slate-200 max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Cabecera del Modal */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 bg-indigo-100 text-indigo-800 rounded-lg">
              <Scale className="w-5 h-5" />
            </div>
            <div>
              <h3 id="decision-modal-title" className="text-base font-bold text-slate-900">
                Registrar Decisión de Negocio
              </h3>
              <p className="text-xs text-slate-500">
                Formalización explícita de alternativas analíticas, criterios y estado de adopción.
              </p>
            </div>
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

        {/* Barra de Plantilla Rápida */}
        <div className="bg-indigo-50/70 border-b border-indigo-100 px-6 py-2.5 flex items-center justify-between text-xs">
          <div className="flex items-center space-x-2 text-indigo-900 font-medium">
            <Sparkles className="w-4 h-4 text-indigo-600" />
            <span>¿Evaluar alternativas analíticas para M1?</span>
          </div>
          <button
            type="button"
            onClick={handleLoadTemplate}
            className="px-2.5 py-1 text-xs font-semibold rounded-md bg-indigo-600 hover:bg-indigo-700 text-white transition-colors"
          >
            Cargar Plantilla M1
          </button>
        </div>

        {/* Cuerpo del Formulario */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-4 text-xs">
          {submitError && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-800 flex items-start space-x-2">
              <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold">Error al registrar la decisión</p>
                <p className="text-[11px] font-mono mt-0.5">{submitError}</p>
              </div>
            </div>
          )}

          {/* Tipo de Decisión */}
          <div>
            <label htmlFor="decision-type" className="block font-semibold text-slate-700 mb-1">
              Tipo de Decisión (decision_type) <span className="text-rose-500">*</span>
            </label>
            <input
              id="decision-type"
              type="text"
              value={decisionType}
              onChange={(e) => setDecisionType(e.target.value)}
              placeholder="Ej. select_alternative, feature_selection, metric_threshold"
              maxLength={64}
              className="w-full text-xs rounded-lg border border-slate-300 px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            {fieldErrors.decisionType && (
              <p className="text-[11px] text-rose-600 mt-1">{fieldErrors.decisionType}</p>
            )}
          </div>

          {/* Pregunta */}
          <div>
            <label htmlFor="decision-question" className="block font-semibold text-slate-700 mb-1">
              Pregunta de Decisión (question) <span className="text-rose-500">*</span>
            </label>
            <textarea
              id="decision-question"
              rows={2}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ej. ¿Qué estrategia de modelado analítico debe implementarse para este problema?"
              className="w-full text-xs rounded-lg border border-slate-300 px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            {fieldErrors.question && (
              <p className="text-[11px] text-rose-600 mt-1">{fieldErrors.question}</p>
            )}
          </div>

          {/* Opciones a Evaluar (StringListInput) */}
          <div className="pt-2 border-t border-slate-100">
            <StringListInput
              id="decision-options-input"
              label="Opciones a Evaluar (options)"
              description="Añade las alternativas consideradas (mínimo 1 opción requerida)."
              placeholder="Ej. supervised_tabular_classification"
              items={options}
              onChange={(newOptions) => {
                setOptions(newOptions);
                if (selectedOption && !newOptions.includes(selectedOption)) {
                  setSelectedOption('');
                }
              }}
              required
              minItems={1}
              errorMessage={fieldErrors.options}
            />
          </div>

          {/* Justificación (Rationale) */}
          <div className="pt-2 border-t border-slate-100">
            <label htmlFor="decision-rationale" className="block font-semibold text-slate-700 mb-1">
              Justificación / Argumentación (rationale)
            </label>
            <textarea
              id="decision-rationale"
              rows={2}
              value={rationale}
              onChange={(e) => setRationale(e.target.value)}
              placeholder="Ej. Se prioriza precisión interpretable sobre caja negra debido a regulaciones bancarias."
              className="w-full text-xs rounded-lg border border-slate-300 px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {/* Estado de la Decisión */}
          <div className="pt-2 border-t border-slate-100">
            <label htmlFor="decision-status" className="block font-semibold text-slate-700 mb-1">
              Estado de la Decisión (status) <span className="text-rose-500">*</span>
            </label>
            <select
              id="decision-status"
              value={status}
              onChange={(e) => setStatus(e.target.value as DecisionStatus)}
              className="w-full text-xs rounded-lg border border-slate-300 px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
            >
              <option value="pending">pending (Pendiente de evaluación)</option>
              <option value="decided">decided (Resuelta / Opción adoptada)</option>
              <option value="rejected">rejected (Descartada / Rechazada)</option>
            </select>
          </div>

          {/* Campos condicionales si status === 'decided' */}
          {status === 'decided' && (
            <div className="p-3.5 bg-indigo-50/60 rounded-xl border border-indigo-100 space-y-3 animate-in fade-in duration-150">
              <h4 className="text-xs font-bold text-indigo-950 flex items-center space-x-1.5">
                <Scale className="w-3.5 h-3.5 text-indigo-700" />
                <span>Parámetros de Resolución de Decisión</span>
              </h4>

              {/* Opción Seleccionada (Select desde options) */}
              <div>
                <label
                  htmlFor="decision-selected-option"
                  className="block font-semibold text-indigo-900 mb-1"
                >
                  Opción Seleccionada (selected_option) <span className="text-rose-500">*</span>
                </label>
                {options.length === 0 ? (
                  <p className="text-[11px] text-amber-700 italic">
                    Añade primero opciones en la lista superior para poder seleccionar la adoptada.
                  </p>
                ) : (
                  <select
                    id="decision-selected-option"
                    value={selectedOption}
                    onChange={(e) => setSelectedOption(e.target.value)}
                    className="w-full text-xs rounded-lg border border-indigo-200 px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                  >
                    <option value="">-- Selecciona una de las opciones disponibles --</option>
                    {options.map((opt, idx) => (
                      <option key={idx} value={opt}>
                        {opt}
                      </option>
                    ))}
                  </select>
                )}
                {fieldErrors.selectedOption && (
                  <p className="text-[11px] text-rose-600 mt-1">{fieldErrors.selectedOption}</p>
                )}
              </div>

              {/* Responsable de la Decisión */}
              <div>
                <label
                  htmlFor="decision-decided-by"
                  className="block font-semibold text-indigo-900 mb-1"
                >
                  Responsable / Autor de la Decisión (decided_by) <span className="text-rose-500">*</span>
                </label>
                <input
                  id="decision-decided-by"
                  type="text"
                  value={decidedBy}
                  onChange={(e) => setDecidedBy(e.target.value)}
                  placeholder="Ej. chief-data-officer"
                  maxLength={128}
                  className="w-full text-xs rounded-lg border border-indigo-200 px-3 py-2 text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                />
                {fieldErrors.decidedBy && (
                  <p className="text-[11px] text-rose-600 mt-1">{fieldErrors.decidedBy}</p>
                )}
              </div>
            </div>
          )}

          {/* Pie del Formulario */}
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
              className="inline-flex items-center space-x-1.5 px-4 py-2 text-xs font-semibold rounded-lg text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 transition-colors shadow-sm"
            >
              {isSubmitting ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Registrando Decisión...</span>
                </>
              ) : (
                <>
                  <Check className="w-3.5 h-3.5" />
                  <span>Registrar Decisión</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
