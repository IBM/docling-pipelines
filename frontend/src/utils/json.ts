
/**
 * Converts a stored property value (object, string, or nullish)
 * to a display string for TextArea.
 */
export const toJsonString = (value: unknown): string => {
  if (value === undefined || value === null) { return ''; }
  if (typeof value === 'object') { return JSON.stringify(value, null, 2); }
  return String(value);
};

export const isValidJsonObject = (value: string): boolean => {
  if (!value.trim()) {
    return true;
  }

  try {
    const parsed = JSON.parse(value);

    return (
      typeof parsed === 'object' &&
      parsed !== null &&
      !Array.isArray(parsed)
    );
  } catch {
    return false;
  }
};
