import React, { useState, useCallback } from 'react';

// Survey dimension types matching the backend model
interface RatingSpec {
  kind: 'rating';
  min: number;
  max: number;
  step: number;
  anchors?: Record<string, string>;
  ui?: {
    control?: 'slider' | 'radio' | 'stars';
    show_value?: boolean;
  };
}

interface TextSpec {
  kind: 'text' | 'long_text';
  min_length?: number;
  max_length?: number;
  placeholder?: string;
}

interface NumberSpec {
  kind: 'number';
  min?: number;
  max?: number;
  integer?: boolean;
  unit?: string;
}

interface ChoiceOption {
  value: string;
  label: string;
}

interface ChoiceSpec {
  kind: 'choice';
  options: ChoiceOption[];
  randomize?: boolean;
}

interface MultiChoiceSpec {
  kind: 'multi_choice';
  options: ChoiceOption[];
  min_selected?: number;
  max_selected?: number;
}

interface BooleanSpec {
  kind: 'boolean';
  true_label?: string;
  false_label?: string;
}

type DimensionSpec =
  | RatingSpec
  | TextSpec
  | NumberSpec
  | ChoiceSpec
  | MultiChoiceSpec
  | BooleanSpec;

interface SurveyDimension {
  name: string;
  label: string;
  spec: DimensionSpec;
  required?: boolean;
  help?: string;
}

interface SurveyFormProps {
  dimensions: SurveyDimension[];
  onSubmit: (ratings: Record<string, unknown>, notes?: string) => void;
  onCancel?: () => void;
  isSubmitting?: boolean;
  showNotes?: boolean;
}

/**
 * Survey form component that renders form fields based on dimension specs.
 */
export default function SurveyForm({
  dimensions,
  onSubmit,
  onCancel,
  isSubmitting = false,
  showNotes = true,
}: SurveyFormProps) {
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [notes, setNotes] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});

  const handleChange = useCallback((name: string, value: unknown) => {
    setValues((prev) => ({ ...prev, [name]: value }));
    // Clear error when user modifies field
    setErrors((prev) => {
      const next = { ...prev };
      delete next[name];
      return next;
    });
  }, []);

  const validate = useCallback(() => {
    const newErrors: Record<string, string> = {};
    for (const dim of dimensions) {
      if (
        dim.required &&
        (values[dim.name] === undefined || values[dim.name] === '')
      ) {
        newErrors[dim.name] = 'This field is required';
      }
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [dimensions, values]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (validate()) {
        onSubmit(values, notes || undefined);
      }
    },
    [validate, onSubmit, values, notes]
  );

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {dimensions.map((dim) => (
        <DimensionField
          key={dim.name}
          dimension={dim}
          value={values[dim.name]}
          onChange={(value) => handleChange(dim.name, value)}
          error={errors[dim.name]}
        />
      ))}

      {showNotes && (
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">
            Additional Notes
            <span className="text-gray-400 font-normal ml-1">(optional)</span>
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="Any additional feedback..."
          />
        </div>
      )}

      <div className="flex justify-end gap-3 pt-4 border-t">
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
          >
            Cancel
          </button>
        )}
        <button
          type="submit"
          disabled={isSubmitting}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50"
        >
          {isSubmitting ? 'Submitting...' : 'Submit Feedback'}
        </button>
      </div>
    </form>
  );
}

interface DimensionFieldProps {
  dimension: SurveyDimension;
  value: unknown;
  onChange: (value: unknown) => void;
  error?: string;
}

function DimensionField({
  dimension,
  value,
  onChange,
  error,
}: DimensionFieldProps) {
  const { name, label, spec, required, help } = dimension;

  return (
    <div className="space-y-2">
      <label htmlFor={name} className="block text-sm font-medium text-gray-700">
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </label>

      {help && <p className="text-xs text-gray-500">{help}</p>}

      <SpecField name={name} spec={spec} value={value} onChange={onChange} />

      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}

interface SpecFieldProps {
  name: string;
  spec: DimensionSpec;
  value: unknown;
  onChange: (value: unknown) => void;
}

function SpecField({ name, spec, value, onChange }: SpecFieldProps) {
  switch (spec.kind) {
    case 'rating':
      return (
        <RatingField
          name={name}
          spec={spec}
          value={value as number | undefined}
          onChange={onChange}
        />
      );
    case 'text':
    case 'long_text':
      return (
        <TextField
          name={name}
          spec={spec}
          value={value as string | undefined}
          onChange={onChange}
        />
      );
    case 'number':
      return (
        <NumberField
          name={name}
          spec={spec}
          value={value as number | undefined}
          onChange={onChange}
        />
      );
    case 'choice':
      return (
        <ChoiceField
          name={name}
          spec={spec}
          value={value as string | undefined}
          onChange={onChange}
        />
      );
    case 'multi_choice':
      return (
        <MultiChoiceField
          name={name}
          spec={spec}
          value={value as string[] | undefined}
          onChange={onChange}
        />
      );
    case 'boolean':
      return (
        <BooleanField
          name={name}
          spec={spec}
          value={value as boolean | undefined}
          onChange={onChange}
        />
      );
    default:
      return (
        <div className="text-gray-400 text-sm">Unsupported field type</div>
      );
  }
}

function RatingField({
  name,
  spec,
  value,
  onChange,
}: {
  name: string;
  spec: RatingSpec;
  value: number | undefined;
  onChange: (value: number) => void;
}) {
  const { min, max, step, anchors, ui } = spec;
  const control = ui?.control ?? 'slider';
  const showValue = ui?.show_value ?? true;

  // Generate all possible values
  const steps = [];
  for (let i = min; i <= max; i += step) {
    steps.push(i);
  }

  if (control === 'slider') {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-4">
          <input
            type="range"
            id={name}
            min={min}
            max={max}
            step={step}
            value={value ?? min}
            onChange={(e) => onChange(Number(e.target.value))}
            className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
          />
          {showValue && (
            <span className="w-8 text-center text-lg font-semibold text-blue-600">
              {value ?? '-'}
            </span>
          )}
        </div>
        {anchors && (
          <div className="flex justify-between text-xs text-gray-500">
            {steps.map((v) => (
              <span
                key={v}
                className={value === v ? 'font-medium text-blue-600' : ''}
              >
                {anchors[String(v)] || v}
              </span>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (control === 'radio') {
    return (
      <div className="flex gap-4 flex-wrap">
        {steps.map((v) => (
          <label key={v} className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name={name}
              value={v}
              checked={value === v}
              onChange={() => onChange(v)}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm">{anchors?.[String(v)] || v}</span>
          </label>
        ))}
      </div>
    );
  }

  // Stars
  return (
    <div className="flex gap-1">
      {steps.map((v) => (
        <button
          key={v}
          type="button"
          onClick={() => onChange(v)}
          className={`text-2xl transition-colors ${
            value !== undefined && v <= value
              ? 'text-yellow-400'
              : 'text-gray-300'
          } hover:text-yellow-400`}
        >
          ★
        </button>
      ))}
    </div>
  );
}

function TextField({
  name,
  spec,
  value,
  onChange,
}: {
  name: string;
  spec: TextSpec;
  value: string | undefined;
  onChange: (value: string) => void;
}) {
  const isLongText = spec.kind === 'long_text';

  if (isLongText) {
    return (
      <textarea
        id={name}
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        maxLength={spec.max_length}
        placeholder={spec.placeholder}
        rows={4}
        className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
    );
  }

  return (
    <input
      type="text"
      id={name}
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
      maxLength={spec.max_length}
      placeholder={spec.placeholder}
      className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
    />
  );
}

function NumberField({
  name,
  spec,
  value,
  onChange,
}: {
  name: string;
  spec: NumberSpec;
  value: number | undefined;
  onChange: (value: number) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <input
        type="number"
        id={name}
        value={value ?? ''}
        onChange={(e) => onChange(Number(e.target.value))}
        min={spec.min}
        max={spec.max}
        step={spec.integer ? 1 : 'any'}
        className="w-32 rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
      {spec.unit && <span className="text-sm text-gray-500">{spec.unit}</span>}
    </div>
  );
}

function ChoiceField({
  name,
  spec,
  value,
  onChange,
}: {
  name: string;
  spec: ChoiceSpec;
  value: string | undefined;
  onChange: (value: string) => void;
}) {
  return (
    <select
      id={name}
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
    >
      <option value="">Select an option...</option>
      {spec.options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}

function MultiChoiceField({
  name,
  spec,
  value,
  onChange,
}: {
  name: string;
  spec: MultiChoiceSpec;
  value: string[] | undefined;
  onChange: (value: string[]) => void;
}) {
  const selected = value ?? [];

  const handleToggle = (optValue: string) => {
    if (selected.includes(optValue)) {
      onChange(selected.filter((v) => v !== optValue));
    } else {
      if (spec.max_selected && selected.length >= spec.max_selected) {
        return;
      }
      onChange([...selected, optValue]);
    }
  };

  return (
    <div className="space-y-2">
      {spec.options.map((opt) => (
        <label
          key={opt.value}
          className="flex items-center gap-2 cursor-pointer"
        >
          <input
            type="checkbox"
            name={name}
            value={opt.value}
            checked={selected.includes(opt.value)}
            onChange={() => handleToggle(opt.value)}
            className="h-4 w-4 text-blue-600 focus:ring-blue-500 rounded"
          />
          <span className="text-sm">{opt.label}</span>
        </label>
      ))}
    </div>
  );
}

function BooleanField({
  name,
  spec,
  value,
  onChange,
}: {
  name: string;
  spec: BooleanSpec;
  value: boolean | undefined;
  onChange: (value: boolean) => void;
}) {
  const trueLabel = spec.true_label ?? 'Yes';
  const falseLabel = spec.false_label ?? 'No';

  return (
    <div className="flex gap-4">
      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="radio"
          name={name}
          checked={value === true}
          onChange={() => onChange(true)}
          className="h-4 w-4 text-blue-600 focus:ring-blue-500"
        />
        <span className="text-sm">{trueLabel}</span>
      </label>
      <label className="flex items-center gap-2 cursor-pointer">
        <input
          type="radio"
          name={name}
          checked={value === false}
          onChange={() => onChange(false)}
          className="h-4 w-4 text-blue-600 focus:ring-blue-500"
        />
        <span className="text-sm">{falseLabel}</span>
      </label>
    </div>
  );
}
