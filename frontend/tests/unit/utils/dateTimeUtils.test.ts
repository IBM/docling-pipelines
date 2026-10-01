import { describe, it, expect } from 'vitest';
import {
  convertToEpoch,
  convertFromEpoch,
  isEpochValue,
  formatEpochToDisplay,
  formatElapsedTime,
} from '@/utils/dateTimeUtils';

describe('convertToEpoch', () => {
  it('converts valid datetime string to epoch', () => {
    // 2024-01-15 14:30:00 UTC
    const epoch = convertToEpoch('2024-01-15 14:30:00');
    expect(epoch).toBe(1705329000);
  });

  it('returns 0 for empty string', () => {
    expect(convertToEpoch('')).toBe(0);
  });

  it('returns 0 for malformed string', () => {
    expect(convertToEpoch('not-a-date')).toBe(0);
    expect(convertToEpoch('2024/01/15')).toBe(0);
  });

  it('UTC round-trip: convertFromEpoch(convertToEpoch(x)) === x', () => {
    const input = '2024-06-20 10:15:30';
    const epoch = convertToEpoch(input);
    expect(convertFromEpoch(epoch)).toBe(input);
  });
});

describe('convertFromEpoch', () => {
  it('converts valid epoch number to datetime string', () => {
    expect(convertFromEpoch(1705329000)).toBe('2024-01-15 14:30:00');
  });

  it('returns empty string for NaN', () => {
    expect(convertFromEpoch(NaN)).toBe('');
  });

  it('parses numeric string input', () => {
    expect(convertFromEpoch('1705329000')).toBe('2024-01-15 14:30:00');
  });
});

describe('isEpochValue', () => {
  it('returns true for a number >= MIN_EPOCH (946684800)', () => {
    expect(isEpochValue(1705329000)).toBe(true);
  });

  it('returns false for small number below MIN_EPOCH', () => {
    expect(isEpochValue(100)).toBe(false);
  });

  it('returns true for digit string >= 10 chars and >= MIN_EPOCH', () => {
    expect(isEpochValue('1705329000')).toBe(true);
  });

  it('returns false for short digit string', () => {
    expect(isEpochValue('12345')).toBe(false);
  });

  it('returns false for non-digit string', () => {
    expect(isEpochValue('not-a-timestamp')).toBe(false);
    expect(isEpochValue('2024-01-15')).toBe(false);
  });
});

describe('formatEpochToDisplay', () => {
  it('returns non-empty string for valid epoch', () => {
    const result = formatEpochToDisplay(1705329000);
    expect(result).toBeTruthy();
    expect(typeof result).toBe('string');
  });

  it('returns empty string for 0', () => {
    expect(formatEpochToDisplay(0)).toBe('');
  });
});

describe('formatElapsedTime', () => {
  it('formats 0 seconds as "00:00:00"', () => {
    expect(formatElapsedTime(0)).toBe('00:00:00');
  });

  it('formats 154 seconds as "00:02:34"', () => {
    expect(formatElapsedTime(154)).toBe('00:02:34');
  });

  it('formats 3600 seconds as "01:00:00"', () => {
    expect(formatElapsedTime(3600)).toBe('01:00:00');
  });

  it('formats 86399 seconds as "23:59:59"', () => {
    expect(formatElapsedTime(86399)).toBe('23:59:59');
  });
});
