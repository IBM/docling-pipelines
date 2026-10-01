import { vi } from 'vitest';

// Silent log4js stub — replaces the real logger with vi.fn() mocks so no
// output occurs and no actual log4js configuration is required during tests.

const createSilentLogger = (category = 'root') => ({
  category,
  level: 'OFF',
  debug: vi.fn(),
  info: vi.fn(),
  warn: vi.fn(),
  error: vi.fn(),
  fatal: vi.fn(),
  trace: vi.fn(),
  isDebugEnabled: vi.fn(() => false),
  isInfoEnabled: vi.fn(() => false),
  isWarnEnabled: vi.fn(() => false),
  isErrorEnabled: vi.fn(() => false),
  addContext: vi.fn(),
  removeContext: vi.fn(),
  clearContext: vi.fn(),
});

const loggerCache: Record<string, ReturnType<typeof createSilentLogger>> = {};

export const getLogger = vi.fn().mockImplementation((category = 'default') => {
  if (!loggerCache[category]) {
    loggerCache[category] = createSilentLogger(category);
  }
  return loggerCache[category];
});

export const configure = vi.fn();

export default {
  getLogger,
  configure,
};
