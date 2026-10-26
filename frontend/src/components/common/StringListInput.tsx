import React, { useState } from 'react';
import { Plus, X, AlertCircle } from 'lucide-react';

interface StringListInputProps {
  id: string;
  label: string;
  description?: string;
  items: string[];
  onChange: (items: string[]) => void;
  placeholder?: string;
  required?: boolean;
  minItems?: number;
  maxItems?: number;
  errorMessage?: string;
}

export const StringListInput: React.FC<StringListInputProps> = ({
  id,
  label,
  description,
  items,
  onChange,
  placeholder = 'Escribe un elemento y pulsa Añadir...',
  required = false,
  minItems = 0,
  maxItems = 100,
  errorMessage,
}) => {
  const [inputValue, setInputValue] = useState('');
  const [inputError, setInputError] = useState<string | null>(null);

  const handleAddItem = () => {
    const trimmed = inputValue.trim();
    if (!trimmed) {
      setInputError('El elemento no puede estar vacío');
      return;
    }
    if (items.length >= maxItems) {
      setInputError(`No se pueden añadir más de ${maxItems} elementos`);
      return;
    }
    onChange([...items, trimmed]);
    setInputValue('');
    setInputError(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddItem();
    }
  };

  const handleRemoveItem = (index: number) => {
    const updated = items.filter((_, i) => i !== index);
    onChange(updated);
  };

  const isBelowMin = minItems > 0 && items.length < minItems;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <label htmlFor={id} className="block text-xs font-semibold text-slate-700">
          {label} {required && <span className="text-rose-500">*</span>}
        </label>
        <span className="text-[11px] text-slate-400">
          {items.length} {items.length === 1 ? 'elemento' : 'elementos'}
          {minItems > 0 && ` (mínimo ${minItems})`}
        </span>
      </div>

      {description && <p className="text-[11px] text-slate-500">{description}</p>}

      <div className="flex space-x-2">
        <input
          id={id}
          type="text"
          value={inputValue}
          onChange={(e) => {
            setInputValue(e.target.value);
            if (inputError) setInputError(null);
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="flex-1 text-xs rounded-lg border border-slate-300 px-3 py-2 text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition-colors"
        />
        <button
          type="button"
          onClick={handleAddItem}
          className="inline-flex items-center space-x-1 px-3 py-2 text-xs font-medium rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition-colors shadow-sm"
          aria-label={`Añadir a ${label}`}
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Añadir</span>
        </button>
      </div>

      {inputError && (
        <p className="text-[11px] text-rose-600 flex items-center space-x-1">
          <AlertCircle className="w-3 h-3 flex-shrink-0" />
          <span>{inputError}</span>
        </p>
      )}

      {errorMessage && (
        <p className="text-[11px] text-rose-600 flex items-center space-x-1">
          <AlertCircle className="w-3 h-3 flex-shrink-0" />
          <span>{errorMessage}</span>
        </p>
      )}

      {isBelowMin && !errorMessage && (
        <p className="text-[11px] text-amber-600 flex items-center space-x-1">
          <AlertCircle className="w-3 h-3 flex-shrink-0" />
          <span>Debes agregar al menos {minItems} {minItems === 1 ? 'criterio' : 'criterios'}.</span>
        </p>
      )}

      {/* List of items */}
      {items.length > 0 && (
        <ul className="mt-2 space-y-1.5 max-h-36 overflow-y-auto pr-1">
          {items.map((item, index) => (
            <li
              key={index}
              className="flex items-center justify-between px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs text-slate-800 group"
            >
              <span className="font-mono text-[11px] text-slate-400 mr-2 flex-shrink-0">
                #{index + 1}
              </span>
              <span className="flex-1 truncate">{item}</span>
              <button
                type="button"
                onClick={() => handleRemoveItem(index)}
                className="text-slate-400 hover:text-rose-600 ml-2 p-0.5 rounded transition-colors"
                aria-label={`Eliminar elemento ${index + 1}`}
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
