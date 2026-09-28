import type { SharedDataTableHeader } from '@/components/common/SharedDataTable';
import { API_STATUS_MAP } from './flowStatus';

export const DEFAULT_TABLE_PAGE_SIZES = [10, 25, 50] as const;
export const DEFAULT_TABLE_PAGE_SIZE = 50;

/**
 * Set of API status strings for which the Logs download button is enabled
 * in the run history tearsheet. Mirrors datasift-ui's `downloadLogsStatusList`.
 *
 * Derived from `API_STATUS_MAP` so it stays in sync with every known status
 * automatically — no manual list to maintain.
 */
export const DOWNLOAD_ENABLED_STATUSES = new Set(Object.keys(API_STATUS_MAP));

export const FLOW_RUN_HISTORY_TITLE = 'Flow run history';

export const FLOW_RUN_HISTORY_HEADERS: SharedDataTableHeader[] = [
  { key: 'timestamp', header: 'Timestamp' },
  { key: 'status',    header: 'Status'    },
  { key: 'duration',  header: 'Duration'  },
  { key: 'logs',      header: 'Logs'      },
];
