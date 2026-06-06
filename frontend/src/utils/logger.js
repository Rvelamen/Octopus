/**
 * Conditional logger - only logs in development mode.
 * Use this instead of raw console.log/console.warn.
 */

const isDev = import.meta.env?.DEV ?? true;

export const logger = {
  debug: (...args) => {
    if (isDev) console.debug("[DEBUG]", ...args);
  },
  info: (...args) => {
    if (isDev) console.info("[INFO]", ...args);
  },
  warn: (...args) => {
    console.warn("[WARN]", ...args);
  },
  error: (...args) => {
    console.error("[ERROR]", ...args);
  },
};
