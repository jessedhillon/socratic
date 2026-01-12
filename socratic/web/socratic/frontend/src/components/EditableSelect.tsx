import React, { useState } from 'react';

interface Option {
  value: string;
  label: string;
}

interface EditableSelectProps {
  value: string;
  options: Option[];
  onChange: (value: string) => void;
  onSave?: () => void;
  className?: string;
  textClassName?: string;
}

/**
 * Inline editable select component styled as prose.
 * Shows edit icon on hover, reveals select dropdown styling on click.
 */
const EditableSelect: React.FC<EditableSelectProps> = ({
  value,
  options,
  onChange,
  onSave,
  className = '',
  textClassName = '',
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [isHovered, setIsHovered] = useState(false);

  const selectedOption = options.find((o) => o.value === value);

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onChange(e.target.value);
    setIsEditing(false);
    onSave?.();
  };

  const handleBlur = () => {
    setIsEditing(false);
  };

  const baseClasses = `
    rounded px-2 py-1 -mx-2 -my-1
    transition-all duration-150
    ${isEditing ? 'bg-blue-50/50' : ''}
  `;

  // Edit icon (pencil)
  const EditIcon = () => (
    <svg
      className={`inline-block w-4 h-4 ml-2 transition-opacity duration-150 ${
        isHovered && !isEditing ? 'opacity-60' : 'opacity-0'
      }`}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
      />
    </svg>
  );

  if (isEditing) {
    return (
      <div className={className}>
        <select
          value={value}
          onChange={handleChange}
          onBlur={handleBlur}
          autoFocus
          className={`${baseClasses} ${textClassName} bg-transparent focus:outline-none cursor-pointer`}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
    );
  }

  return (
    <div
      className={className}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={() => setIsEditing(true)}
    >
      <span
        className={`${baseClasses} ${textClassName} cursor-pointer inline-block`}
      >
        {selectedOption?.label || value}
        <EditIcon />
      </span>
    </div>
  );
};

export default EditableSelect;
