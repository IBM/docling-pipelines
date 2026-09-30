import { describe, it, expect } from 'vitest';
import { toJsonString, isValidJsonObject } from '@/utils/json';

describe('toJsonString', () => {
  it('returns empty string for undefined', () => {
    expect(toJsonString(undefined)).toBe('');
  });

  it('returns empty string for null', () => {
    expect(toJsonString(null)).toBe('');
  });

  it('converts object to pretty JSON string', () => {
    const obj = { key: 'value', num: 42 };
    const result = toJsonString(obj);
    expect(result).toBe(JSON.stringify(obj, null, 2));
  });

  it('passes string through unchanged', () => {
    expect(toJsonString('hello')).toBe('hello');
  });

  it('converts number to string', () => {
    expect(toJsonString(123)).toBe('123');
  });
});

describe('isValidJsonObject', () => {
  it('returns true for valid object string', () => {
    expect(isValidJsonObject('{"key":"value"}')).toBe(true);
  });

  it('returns true for empty/whitespace string', () => {
    expect(isValidJsonObject('')).toBe(true);
    expect(isValidJsonObject('   ')).toBe(true);
  });

  it('returns false for array string', () => {
    expect(isValidJsonObject('[1,2,3]')).toBe(false);
  });

  it('returns false for string literal', () => {
    expect(isValidJsonObject('"hello"')).toBe(false);
  });

  it('returns false for malformed JSON', () => {
    expect(isValidJsonObject('{invalid}')).toBe(false);
  });

  it('returns false for null JSON', () => {
    expect(isValidJsonObject('null')).toBe(false);
  });
});
