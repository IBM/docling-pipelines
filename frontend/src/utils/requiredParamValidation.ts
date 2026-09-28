/**
 * @file Required-parameter validation utilities for operator properties panels.
 *
 * Usage:
 * const validate = getRequiredParamValidator(nodeAttributes);
 *
 * const result = validate(ATTR.PROVIDER, provider, LABEL.PROVIDER);
 * <Dropdown invalid={result.isInvalid} invalidText={result.errorMessage} ... />
 *
 * The validator reads `required` from the operator metadata attributes object
 * and compares it against the current value.
 */

import type { OperatorFeature } from '@/types';

export interface ValidationResult {
  isInvalid: boolean;
  errorMessage: string;
}

/**
 * Function signature for the validator returned by `getRequiredParamValidator`.
 *
 * @param paramId — the attribute key (must match `nodeAttributes` key)
 * @param value   — the current field value
 */
export type RequiredParamValidator = (
  paramId: string,
  value: unknown,
) => ValidationResult;

/**
 * Returns true when `value` is considered empty for required parameter purposes.
 * Covers: undefined, null, empty string, and empty arrays.
 */
const isMissing = (value: unknown): boolean =>
  value === undefined ||
  value === null ||
  value === '' ||
  (Array.isArray(value) && value.length === 0);

/**
 * Returns a `RequiredParamValidator` bound to the given operator attributes.
 *
 * @param nodeAttributes — `OperatorMetadata.attributes` for the operator being configured
 */
export const getRequiredParamValidator = (
  nodeAttributes: Record<string, OperatorFeature>
): RequiredParamValidator =>
  (paramId, value): ValidationResult => {
    const attr = nodeAttributes[paramId];
    if (!attr?.required) {
      return { isInvalid: false, errorMessage: '' };
    }
    const invalid = isMissing(value);
    return {
      isInvalid: invalid,
      errorMessage: invalid ? 'This is a required parameter.' : '',
    };
  };

/**
 * Checks all required attributes in `nodeAttributes` against the current
 * property values returned by `getPropertyValues()` and returns `true` when
 * at least one required param is missing.
 *
 * Intended to drive `controller.setSaveButtonDisable`.
 *
 * @param nodeAttributes  — `OperatorMetadata.attributes` for the current operator
 * @param propertyValues  — Map of paramId → current value (from `controller.getPropertyValues()`)
 */
export const hasAnyRequiredParamMissing = (
  nodeAttributes: Record<string, OperatorFeature>,
  propertyValues: Record<string, unknown>
): boolean =>
  Object.entries(nodeAttributes).some(
    ([paramId, attr]) => attr.required && isMissing(propertyValues[paramId])
  );
