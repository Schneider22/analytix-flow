import React from 'react';
import { AlternativeComparison, DecisionRead } from '../../types/projects';
import {
  Layers,
  CheckCircle2,
  AlertCircle,
  Database,
  ShieldAlert,
  Award,
  Sparkles,
  Info,
} from 'lucide-react';

interface AlternativesMatrixProps {
  decisions: DecisionRead[];
  onOpenDecisionModal?: () => void;
}

const M1_STANDARD_ALTERNATIVES: AlternativeComparison[] = [
  {
    id: 'supervised_tabular_classification',
    name: 'Clasificación Supervisada Tabular',
    approach:
      'Modelado predictivo basado en algoritmos de ensamble (Gradient Boosting / Random Forest) sobre variables estructuradas históricas.',
    suitability:
      'Óptimo cuando existen registros históricos suficientes y la meta es predecir una propensión binaria o multiclase de negocio.',
    data_requirements:
      'Datos tabulares estructurados con etiquetas de resultado verificadas y cobertura temporal suficiente.',
    estimated_complexity: 'Media',
    risks_and_limitations:
      'Sensible a desbalance de clases, deriva conceptual (concept drift) y sobreajuste si la muestra es reducida.',
    empirical_evidence_level: 'Alto',
  },
  {
    id: 'heuristic_business_rule_engine',
    name: 'Motor Heurístico de Reglas de Negocio',
    approach:
      'Sistema determinista basado en árboles de decisión operacionales y reglas condicionales derivadas de políticas de negocio y conocimiento experto.',
    suitability:
      'Adecuado cuando los datos etiquetados son escasos o la normativa exige explicabilidad determinista total.',
    data_requirements:
      'Definición formal de políticas de corte, límites operacionales y variables de perfil básico del sujeto.',
    estimated_complexity: 'Baja',
    risks_and_limitations:
      'Baja adaptabilidad a interacciones no lineales, rigidez ante cambios de mercado y costo elevado de mantenimiento de reglas.',
    empirical_evidence_level: 'Medio',
  },
  {
    id: 'unsupervised_anomaly_clustering',
    name: 'Detección de Anomalías y Agrupamiento',
    approach:
      'Descubrimiento no supervisado de patrones atípicos y agrupamiento por similitud de atributos sin requerir etiquetas previas.',
    suitability:
      'Idóneo para análisis exploratorio temprano o detección de eventos poco frecuentes sin verdad terreno (ground truth).',
    data_requirements:
      'Variables tabulares continuas y categóricas normalizadas, sin obligatoriedad de target histórico previo.',
    estimated_complexity: 'Media',
    risks_and_limitations:
      'Complejidad para evaluar cuantitativamente la precisión sin etiquetas y necesidad de interpretación humana experta.',
    empirical_evidence_level: 'Preliminar',
  },
];

export const AlternativesMatrix: React.FC<AlternativesMatrixProps> = ({
  decisions,
  onOpenDecisionModal,
}) => {
  // Find if there is an adopted decision for select_alternative
  const alternativeDecision = decisions.find(
    (d) => d.decision_type === 'select_alternative' && d.status === 'decided' && d.selected_option
  );
  const adoptedOptionId = alternativeDecision?.selected_option ?? null;

  const renderComplexityBadge = (complexity: AlternativeComparison['estimated_complexity']) => {
    switch (complexity) {
      case 'Baja':
        return (
          <span className="px-2 py-0.5 text-[10px] font-semibold rounded bg-emerald-100 text-emerald-800">
            Baja
          </span>
        );
      case 'Media':
        return (
          <span className="px-2 py-0.5 text-[10px] font-semibold rounded bg-amber-100 text-amber-800">
            Media
          </span>
        );
      case 'Alta':
        return (
          <span className="px-2 py-0.5 text-[10px] font-semibold rounded bg-rose-100 text-rose-800">
            Alta
          </span>
        );
    }
  };

  const renderEvidenceBadge = (level: AlternativeComparison['empirical_evidence_level']) => {
    switch (level) {
      case 'Alto':
        return (
          <span className="px-2 py-0.5 text-[10px] font-semibold rounded bg-emerald-100 text-emerald-800 border border-emerald-200">
            Evidencia Alta
          </span>
        );
      case 'Medio':
        return (
          <span className="px-2 py-0.5 text-[10px] font-semibold rounded bg-blue-100 text-blue-800 border border-blue-200">
            Evidencia Media
          </span>
        );
      case 'Preliminar':
        return (
          <span className="px-2 py-0.5 text-[10px] font-semibold rounded bg-purple-100 text-purple-800 border border-purple-200">
            Evidencia Preliminar
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Encabezado */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <div className="flex items-center space-x-2">
            <h3 className="text-base font-bold text-slate-900">
              Matriz Comparativa de Alternativas Analíticas (M1)
            </h3>
            <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-slate-100 text-slate-700 border border-slate-200">
              3 alternativas
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Evaluación técnica cualitativa y evidencia empírica sustentada para la resolución del problema de negocio.
          </p>
        </div>

        {onOpenDecisionModal && !alternativeDecision && (
          <button
            type="button"
            onClick={onOpenDecisionModal}
            className="inline-flex items-center space-x-1.5 px-3.5 py-2 text-xs font-semibold rounded-lg text-white bg-indigo-600 hover:bg-indigo-700 transition-colors shadow-sm self-start sm:self-auto"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Formalizar Selección</span>
          </button>
        )}
      </div>

      {/* Nota de rigor metodológico */}
      <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-700 text-xs flex items-start space-x-2.5">
        <Info className="w-4 h-4 text-slate-500 flex-shrink-0 mt-0.5" />
        <p className="text-[11px] leading-relaxed">
          Conforme a los lineamientos rectores de AnalytixFlow, las alternativas se comparan por idoneidad,
          complejidad orientativa y nivel de evidencia empírica documentada. No se presentan porcentajes de
          probabilidad arbitrarios no calibrados empíricamente.
        </p>
      </div>

      {/* Banner de Alternativa Adoptada si existe */}
      {alternativeDecision && (
        <div
          data-testid="adopted-alternative-banner"
          className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl flex items-start space-x-3 text-xs text-emerald-950"
        >
          <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-bold text-sm text-emerald-900">
                Alternativa Adoptada por el Negocio:
              </span>
              <span className="px-2.5 py-0.5 rounded-full font-mono font-bold bg-emerald-200 text-emerald-900 text-xs">
                {alternativeDecision.selected_option}
              </span>
            </div>
            {alternativeDecision.rationale && (
              <p className="text-emerald-800 text-xs mt-1">
                <strong>Justificación registrada:</strong> {alternativeDecision.rationale}
              </p>
            )}
            <div className="text-[11px] text-emerald-700 pt-1">
              Formalizado por: <strong>{alternativeDecision.decided_by || 'Responsable'}</strong>{' '}
              {alternativeDecision.decided_at &&
                `(${new Date(alternativeDecision.decided_at).toLocaleDateString()})`}
            </div>
          </div>
        </div>
      )}

      {/* Tarjetas Comparativas de Alternativas */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {M1_STANDARD_ALTERNATIVES.map((alt) => {
          const isAdopted = adoptedOptionId === alt.id;

          return (
            <div
              key={alt.id}
              data-testid={`alternative-card-${alt.id}`}
              className={`rounded-xl border p-5 flex flex-col justify-between space-y-4 transition-all text-xs ${
                isAdopted
                  ? 'bg-emerald-50/40 border-emerald-400 ring-2 ring-emerald-200 shadow-sm'
                  : 'bg-white border-slate-200 hover:border-slate-300 shadow-xs'
              }`}
            >
              <div className="space-y-3">
                {/* Cabecera de la Alternativa */}
                <div className="space-y-1 border-b border-slate-100 pb-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[10px] font-mono text-slate-400 font-bold uppercase truncate" title={alt.id}>
                      {alt.id}
                    </span>
                    {isAdopted ? (
                      <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300 flex items-center space-x-1">
                        <CheckCircle2 className="w-3 h-3 text-emerald-700" />
                        <span>Adoptada</span>
                      </span>
                    ) : (
                      <span className="text-[10px] text-slate-400 italic">Propuesta</span>
                    )}
                  </div>
                  <h4 className="font-bold text-sm text-slate-900 leading-snug">{alt.name}</h4>
                </div>

                {/* Enfoque */}
                <div>
                  <span className="text-[11px] font-semibold text-slate-500 block mb-0.5 flex items-center space-x-1">
                    <Layers className="w-3.5 h-3.5 text-slate-400" />
                    <span>Enfoque Técnico</span>
                  </span>
                  <p className="text-slate-700 leading-relaxed">{alt.approach}</p>
                </div>

                {/* Idoneidad */}
                <div>
                  <span className="text-[11px] font-semibold text-slate-500 block mb-0.5 flex items-center space-x-1">
                    <AlertCircle className="w-3.5 h-3.5 text-slate-400" />
                    <span>Adecuación al Contexto</span>
                  </span>
                  <p className="text-slate-700 leading-relaxed bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                    {alt.suitability}
                  </p>
                </div>

                {/* Requerimientos de Datos */}
                <div>
                  <span className="text-[11px] font-semibold text-slate-500 block mb-0.5 flex items-center space-x-1">
                    <Database className="w-3.5 h-3.5 text-slate-400" />
                    <span>Datos Requeridos</span>
                  </span>
                  <p className="text-slate-600">{alt.data_requirements}</p>
                </div>

                {/* Riesgos y Limitaciones */}
                <div>
                  <span className="text-[11px] font-semibold text-slate-500 block mb-0.5 flex items-center space-x-1">
                    <ShieldAlert className="w-3.5 h-3.5 text-amber-500" />
                    <span>Riesgos y Limitaciones</span>
                  </span>
                  <p className="text-slate-600 italic bg-amber-50/50 p-2.5 rounded-lg border border-amber-100">
                    {alt.risks_and_limitations}
                  </p>
                </div>
              </div>

              {/* Pie de Evaluación: Complejidad y Evidencia */}
              <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
                <div>
                  <span className="text-[10px] text-slate-400 block mb-0.5">Complejidad</span>
                  {renderComplexityBadge(alt.estimated_complexity)}
                </div>
                <div className="text-right">
                  <span className="text-[10px] text-slate-400 block mb-0.5 flex items-center justify-end space-x-1">
                    <Award className="w-3 h-3 text-slate-400" />
                    <span>Sustento</span>
                  </span>
                  {renderEvidenceBadge(alt.empirical_evidence_level)}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
