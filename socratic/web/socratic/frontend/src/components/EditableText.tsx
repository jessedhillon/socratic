import React, {
  useState,
  useRef,
  useEffect,
  forwardRef,
  useImperativeHandle,
} from 'react';

interface EditableTextProps {
  value: string;
  onChange: (value: string) => void;
  onSave?: () => void;
  placeholder?: string;
  multiline?: boolean;
  className?: string;
  textClassName?: string;
  rows?: number;
}

export interface EditableTextHandle {
  focus: () => void;
}

/**
 * Inline editable text component styled as prose.
 * Shows edit icon on hover, transforms to input on click.
 */
const EditableText = forwardRef<EditableTextHandle, EditableTextProps>(
  (
    {
      value,
      onChange,
      onSave,
      placeholder = 'Click to edit...',
      multiline = false,
      className = '',
      textClassName = '',
      rows = 3,
    },
    ref
  ) => {
    const [isEditing, setIsEditing] = useState(false);
    const [isHovered, setIsHovered] = useState(false);
    const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null);

    useImperativeHandle(ref, () => ({
      focus: () => setIsEditing(true),
    }));

    useEffect(() => {
      if (isEditing && inputRef.current) {
        inputRef.current.focus();
        // Place cursor at end
        const length = inputRef.current.value.length;
        inputRef.current.setSelectionRange(length, length);
      }
    }, [isEditing]);

    const handleBlur = () => {
      setIsEditing(false);
      onSave?.();
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsEditing(false);
      }
      if (e.key === 'Enter' && !multiline) {
        setIsEditing(false);
        onSave?.();
      }
    };

    const baseClasses = `
    w-full rounded px-2 py-1 -mx-2 -my-1
    border-b-2 transition-all duration-150
    ${isEditing ? 'border-blue-500 bg-blue-50/50' : isHovered ? 'border-dotted border-gray-400' : 'border-transparent'}
  `;

    const inputClasses = `
    ${baseClasses}
    bg-transparent focus:outline-none focus:bg-blue-50/50
    ${textClassName}
  `;

    const displayClasses = `
    ${baseClasses}
    cursor-text
    ${textClassName}
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
      if (multiline) {
        return (
          <div className={className}>
            <textarea
              ref={inputRef as React.RefObject<HTMLTextAreaElement>}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onBlur={handleBlur}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              rows={rows}
              className={`${inputClasses} resize-none`}
            />
          </div>
        );
      }

      return (
        <div className={className}>
          <input
            ref={inputRef as React.RefObject<HTMLInputElement>}
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onBlur={handleBlur}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            className={inputClasses}
          />
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
        <span className={displayClasses}>
          {value || <span className="text-gray-400 italic">{placeholder}</span>}
          <EditIcon />
        </span>
      </div>
    );
  }
);

EditableText.displayName = 'EditableText';

export default EditableText;
