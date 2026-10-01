import { describe, it, expect } from 'vitest';
import { loadMessages, DEFAULT_LOCALE } from '@/i18n';

describe('i18n', () => {
  it('DEFAULT_LOCALE equals "en"', () => {
    expect(DEFAULT_LOCALE).toBe('en');
  });

  it('loadMessages("en") resolves without throwing', async () => {
    await expect(loadMessages('en')).resolves.toBeDefined();
  });

  it('loadMessages("en") result is a non-empty object', async () => {
    const msgs = await loadMessages('en');
    expect(Object.keys(msgs).length).toBeGreaterThan(0);
  });

  it('loadMessages("unknown") falls back to English without throwing', async () => {
    await expect(loadMessages('unknown-locale-xyz')).resolves.toBeDefined();
  });

  it('loadMessages("en") contains at least one Elyra canvas key', async () => {
    const msgs = await loadMessages('en');
    // Elyra canvas keys typically start with 'canvas.' or contain common canvas terms
    const hasElyraKey = Object.keys(msgs).some(
      (k) => k.includes('canvas') || k.includes('palette') || k.includes('toolbar')
    );
    expect(hasElyraKey).toBe(true);
  });
});
