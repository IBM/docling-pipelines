import { describe, it, expect } from 'vitest';
import {
  getRequiredParamValidator,
  hasAnyRequiredParamMissing,
} from '@/utils/requiredParamValidation';
import type { OperatorFeature } from '@/types';

const requiredAttr: OperatorFeature = {
  type: 'string',
  description: 'required field',
  required: true,
  default: null,
  available_for_filter: null,
  available_for_vector_db: null,
};

const optionalAttr: OperatorFeature = {
  type: 'string',
  description: 'optional field',
  required: false,
  default: null,
  available_for_filter: null,
  available_for_vector_db: null,
};

const nodeAttributes: Record<string, OperatorFeature> = {
  provider: requiredAttr,
  name: optionalAttr,
};

describe('getRequiredParamValidator', () => {
  const validate = getRequiredParamValidator(nodeAttributes);

  it('non-required attr → always { isInvalid: false }', () => {
    const result = validate('name', '');
    expect(result).toEqual({ isInvalid: false, errorMessage: '' });
  });

  it('required attr with value → { isInvalid: false }', () => {
    const result = validate('provider', 'ollama');
    expect(result).toEqual({ isInvalid: false, errorMessage: '' });
  });

  it('required attr with empty string → { isInvalid: true }', () => {
    const result = validate('provider', '');
    expect(result.isInvalid).toBe(true);
    expect(result.errorMessage).toBe('This is a required parameter.');
  });

  it('required attr with undefined → isInvalid', () => {
    expect(validate('provider', undefined).isInvalid).toBe(true);
  });

  it('required attr with null → isInvalid', () => {
    expect(validate('provider', null).isInvalid).toBe(true);
  });

  it('required attr with empty array → isInvalid', () => {
    expect(validate('provider', []).isInvalid).toBe(true);
  });

  it('required attr with non-empty array → valid', () => {
    expect(validate('provider', ['item']).isInvalid).toBe(false);
  });
});

describe('hasAnyRequiredParamMissing', () => {
  it('all present → false', () => {
    const values = { provider: 'ollama', name: 'test' };
    expect(hasAnyRequiredParamMissing(nodeAttributes, values)).toBe(false);
  });

  it('one required missing → true', () => {
    const values = { provider: '', name: 'test' };
    expect(hasAnyRequiredParamMissing(nodeAttributes, values)).toBe(true);
  });

  it('no required attrs → false', () => {
    const allOptional: Record<string, OperatorFeature> = { name: optionalAttr };
    expect(hasAnyRequiredParamMissing(allOptional, {})).toBe(false);
  });
});
