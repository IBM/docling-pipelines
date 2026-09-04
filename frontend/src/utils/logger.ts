/**
 * Logger utility for frontend application
 */

interface Logger {
  category: string;
  isDebugEnabled: () => boolean;
  isInfoEnabled: () => boolean;
  isWarnEnabled: () => boolean;
  isErrorEnabled: () => boolean;
}

interface LogParams {
  logger: Logger;
  message: string;
  req?: unknown;
  data?: unknown;
}

/* eslint-disable no-undef */
const isDevelopment: boolean = typeof process !== 'undefined'
  ? process.env['NODE_ENV'] === 'development'
  : import.meta.env.DEV;
/* eslint-enable no-undef */

const loggers = new Map<string, Logger>();

const createLogger = (category: string): Logger => {
  if (!loggers.has(category)) {
    loggers.set(category, {
      category,
      isDebugEnabled: () => isDevelopment,
      isInfoEnabled: () => true,
      isWarnEnabled: () => true,
      isErrorEnabled: () => true,
    });
  }
  return loggers.get(category)!;
};

export const log4js = {
  getLogger: (category: string): Logger => createLogger(category),
};

export const logUtil = {
  debug: ({ logger, message, data }: LogParams): void => {
    if (logger.isDebugEnabled()) {
      const prefix = `[${new Date().toISOString()}] [DEBUG] [${logger.category}]`;
      // eslint-disable-next-line no-console
      if (data !== undefined) { console.debug(prefix, message, data); } else { console.debug(prefix, message); }
    }
  },

  info: ({ logger, message, data }: LogParams): void => {
    if (logger.isInfoEnabled()) {
      const prefix = `[${new Date().toISOString()}] [INFO] [${logger.category}]`;
      // eslint-disable-next-line no-console
      if (data !== undefined) { console.info(prefix, message, data); } else { console.info(prefix, message); }
    }
  },

  warn: ({ logger, message, data }: LogParams): void => {
    if (logger.isWarnEnabled()) {
      const prefix = `[${new Date().toISOString()}] [WARN] [${logger.category}]`;
      // eslint-disable-next-line no-console
      if (data !== undefined) { console.warn(prefix, message, data); } else { console.warn(prefix, message); }
    }
  },

  error: ({ logger, message, data }: LogParams): void => {
    if (logger.isErrorEnabled()) {
      const prefix = `[${new Date().toISOString()}] [ERROR] [${logger.category}]`;
      // eslint-disable-next-line no-console
      if (data !== undefined) { console.error(prefix, message, data); } else { console.error(prefix, message); }
    }
  },
};

export default logUtil;
