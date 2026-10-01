import { describe, it, expect } from 'vitest';
import { isVaultReference } from '@/utils/vault';

describe('isVaultReference', () => {
  it('returns true for vault:// reference', () => {
    expect(isVaultReference('vault://secret/key')).toBe(true);
  });

  it('returns false for plain string', () => {
    expect(isVaultReference('plain-value')).toBe(false);
  });

  it('returns false for empty string', () => {
    expect(isVaultReference('')).toBe(false);
  });

  it('returns false for vault: without slashes', () => {
    expect(isVaultReference('vault:secret')).toBe(false);
  });

  it('returns false for non-string values', () => {
    expect(isVaultReference(42)).toBe(false);
    expect(isVaultReference(null)).toBe(false);
    expect(isVaultReference(undefined)).toBe(false);
  });
});
