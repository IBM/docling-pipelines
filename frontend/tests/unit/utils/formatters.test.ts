import { describe, it, expect } from 'vitest';
import {
  formatDate,
  formatDateTime,
  formatNumber,
  formatBytes,
  formatDuration,
  truncate,
} from '@/utils/formatters';

describe('formatDate', () => {
  it('formats a Date object to a readable string', () => {
    const result = formatDate(new Date('2024-01-15'));
    expect(result).toMatch(/Jan/);
    expect(result).toMatch(/2024/);
  });

  it('formats a string date input', () => {
    const result = formatDate('2024-06-01');
    expect(result).toMatch(/Jun/);
    expect(result).toMatch(/2024/);
  });

  it('accepts custom format options', () => {
    const result = formatDate('2024-01-15', { month: 'long', year: 'numeric' });
    expect(result).toMatch(/January/);
    expect(result).toMatch(/2024/);
  });
});

describe('formatDateTime', () => {
  it('includes time in the output', () => {
    const result = formatDateTime('2024-01-15T14:30:00');
    expect(result).toMatch(/Jan/);
    expect(result).toMatch(/2024/);
    // Time portion — AM/PM or 24h clock depending on locale
    expect(result).toMatch(/\d+:\d+/);
  });
});

describe('formatNumber', () => {
  it('formats with thousands separator', () => {
    const result = formatNumber(1234567);
    expect(result).toBe('1,234,567');
  });

  it('formats zero', () => {
    expect(formatNumber(0)).toBe('0');
  });

  it('formats with decimal places', () => {
    const result = formatNumber(1234.5678, 2);
    expect(result).toBe('1,234.57');
  });
});

describe('formatBytes', () => {
  it('returns "0 Bytes" for 0', () => {
    expect(formatBytes(0)).toBe('0 Bytes');
  });

  it('formats KB', () => {
    expect(formatBytes(1024)).toBe('1 KB');
  });

  it('formats MB', () => {
    expect(formatBytes(1024 * 1024)).toBe('1 MB');
  });

  it('formats GB', () => {
    expect(formatBytes(1024 * 1024 * 1024)).toBe('1 GB');
  });
});

describe('formatDuration', () => {
  it('formats seconds only', () => {
    expect(formatDuration(30000)).toBe('30s');
  });

  it('formats minutes and seconds', () => {
    expect(formatDuration(90000)).toBe('1m 30s');
  });

  it('formats hours and minutes', () => {
    expect(formatDuration(3660000)).toBe('1h 1m');
  });

  it('formats zero', () => {
    expect(formatDuration(0)).toBe('0s');
  });
});

describe('truncate', () => {
  it('returns text unchanged when at or under limit', () => {
    expect(truncate('hello', 10)).toBe('hello');
    expect(truncate('hello', 5)).toBe('hello');
  });

  it('truncates with ellipsis when over limit', () => {
    expect(truncate('hello world', 5)).toBe('hello...');
  });

  it('handles exactly at limit (no truncation)', () => {
    expect(truncate('abc', 3)).toBe('abc');
  });
});
