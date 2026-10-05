import { describe, it, expect } from 'vitest';
import { slugify } from '@/lib/helpers/slugify';

describe('slugify', () => {
  it('converts spaces to hyphens', () => {
    expect(slugify('OSS UI Project')).toBe('oss-ui-project');
  });

  it('converts underscores to hyphens', () => {
    expect(slugify('my_flow')).toBe('my-flow');
  });

  it('strips non-alphanumeric characters (no separator inserted)', () => {
    expect(slugify('Flow!@#1')).toBe('flow1');
  });

  it('collapses consecutive hyphens', () => {
    expect(slugify('a--b')).toBe('a-b');
  });

  it('trims leading and trailing hyphens', () => {
    expect(slugify('-hello-')).toBe('hello');
    expect(slugify('___hello___')).toBe('hello');
  });

  it('passes already-lowercase string through', () => {
    expect(slugify('hello-world')).toBe('hello-world');
  });

  it('returns empty string for empty input', () => {
    expect(slugify('')).toBe('');
  });
});
