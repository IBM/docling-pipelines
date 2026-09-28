/**
 * @file Document Classes API actions.
 *
 * All HTTP calls go to the BFF (Node/Express server) which proxies to the
 * Python FastAPI backend. Components should never call the Python backend directly.
 *
 * BFF base: `http://localhost:3001`
 * Python backend base: `http://localhost:8080/api/v1`
 */

import { type AxiosResponse } from 'axios';
import { log4js, logUtil } from '@/utils/logger';
import { type DocumentClassItem } from '@/types';
import { apiClient } from '../client';

const logger = log4js.getLogger('document-class.actions');

const BFF_HEADERS = {
  'Accept': 'application/json',
  'X-Requested-With': 'XMLHttpRequest',
};

/**
 * Fetches all available document classes used to populate the Document
 * Classifier panel's document types multi-select.
 *
 * @remarks
 * BFF endpoint: `GET /api/documentClasses`
 * Python backend: `GET /api/v1/document_classes`
 *
 * On failure the Document Classifier panel degrades gracefully: it shows an
 * inline warning and falls back to a free-text `TextArea`.
 *
 * @returns Axios response wrapping an array of {@link DocumentClassItem}
 * @throws Re-throws any Axios error after logging it
 */
export const getDocumentClasses = async (): Promise<AxiosResponse<DocumentClassItem[]>> => {
  const url = '/api/documentClasses';

  try {
    const response = await apiClient.get<DocumentClassItem[]>(url, { headers: BFF_HEADERS });

    logUtil.info({
      logger,
      message: 'Successfully fetched document classes',
      data: { count: response.data.length },
    });

    return response;

  } catch (error) {
    logUtil.error({
      logger,
      message: 'Failed to fetch document classes',
      data: error,
    });
    throw error;
  }
};
