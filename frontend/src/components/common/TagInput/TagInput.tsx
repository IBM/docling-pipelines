import React, { useState } from 'react';
import { Tag, TextInput } from '@carbon/react';
import styles from './TagInput.module.scss';

/**
 * Props for {@link TagInput}.
 */
interface TagInputProps {
  /**
   * HTML `id` forwarded to the underlying `TextInput`.
   * Also used by the visible `<label>` via `htmlFor`.
   */
  id: string;
  /** Controlled list of current tag strings. */
  tags: string[];
  /** Called with the updated tag array whenever tags are added or removed. */
  onChange: (tags: string[]) => void;
  /** Label text rendered above the chips and input. Defaults to `'Tags (optional)'`. */
  labelText?: string;
  /** When true, the label element is not rendered. Use when the parent already provides a label. */
  hideLabel?: boolean;
  /** Helper text rendered below the input. */
  helperText?: string;
  /** Placeholder shown inside the text input when empty. */
  placeholder?: string;
  /** When true, the input and tag removal are disabled. */
  disabled?: boolean;
}

/**
 * Controlled tag input that renders existing tags as dismissible Carbon chips
 * and lets the user add new tags by typing and pressing Enter or comma.
 *
 * Behaviour:
 * - **Add**: press Enter or `,` to commit the current text as a new tag.
 * - **Blur commit**: if the user clicks away without pressing Enter, any pending
 *   text is committed automatically — prevents tags being silently dropped when
 *   the user clicks Next in a multi-step form.
 * - **Duplicate guard**: adding a tag that already exists is a no-op.
 * - **Remove**: click the `×` on a chip to remove that tag.
 */
export function TagInput({
  id,
  tags,
  onChange,
  labelText = 'Tags (optional)',
  hideLabel = false,
  helperText = 'Add tags to make projects easier to find. To add tags, separate them with commas and press Enter.',
  placeholder = 'Add tags',
  disabled = false,
}: TagInputProps): React.JSX.Element {
  const [inputValue, setInputValue] = useState('');

  /** Trims the value, strips any trailing comma, and appends it as a new tag. */
  const commitPending = (value: string): void => {
    const trimmed = value.trim().replace(/,+$/, '');
    if (trimmed && !tags.includes(trimmed)) {
      onChange([...tags, trimmed]);
    }
    setInputValue('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      commitPending(inputValue);
    }
  };

  // Commit any pending text when focus leaves — ensures tags typed before
  // clicking Next are not lost even if the user never pressed Enter.
  const handleBlur = (): void => {
    if (inputValue.trim()) {
      commitPending(inputValue);
    }
  };

  const handleRemove = (tag: string): void => {
    onChange(tags.filter((t) => t !== tag));
  };

  return (
    <div className={styles.wrapper}>
      {/* Label rendered unless hideLabel is true */}
      {!hideLabel && (
        <label htmlFor={id} className={styles.label}>
          {labelText}
        </label>
      )}

      {/* Chips appear directly below the label when tags exist */}
      {tags.length > 0 && (
        <div className={styles.tagsRow}>
          {tags.map((tag) => (
            <Tag
              key={tag}
              type="gray"
              size="sm"
              filter
              onClose={() => { handleRemove(tag); }}
            >
              {tag}
            </Tag>
          ))}
        </div>
      )}

      {/* hideLabel suppresses the duplicate label on the input itself */}
      <TextInput
        id={id}
        labelText={labelText}
        hideLabel
        placeholder={placeholder}
        value={inputValue}
        onChange={(e) => { setInputValue(e.target.value); }}
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
        helperText={helperText}
        disabled={disabled}
      />
    </div>
  );
}
