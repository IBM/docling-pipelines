/**
 * @file Operators API actions.
 *
 * All HTTP calls go to the BFF (Node/Express server) which proxies to the
 * Python FastAPI backend. Components should never call the Python backend directly.
 *
 * BFF base: `http://localhost:3001`
 * Python backend base: `http://localhost:8080/api/v1`
 */

import { type AppDispatch } from '@/store';
import { log4js, logUtil } from '@/utils/logger';
import type { OperatorsResponse, ModelsResponse } from '@/types';
import { setOperatorMetadata } from '@/slices/operatorsSlice';
import { apiClient } from '../client';
import type { AxiosResponse } from 'axios';

const logger = log4js.getLogger('operators.actions');

const BFF_HEADERS = {
  'Accept': 'application/json',
  'X-Requested-With': 'XMLHttpRequest',
};

/**
 * Fetches operator metadata from the BFF and dispatches it into Redux.
 *
 * @remarks
 * BFF endpoint: `GET /api/fetchOperatorMetadata`
 * Python backend: `GET /api/v1/operators/metadata`
 *
 * Dispatches `setOperatorMetadata` on success so the data is available in
 * Redux and passed into every properties panel via `appData.operatorMetadata`.
 *
 * @param dispatch - Redux dispatch function from the calling component
 * @throws Re-throws any Axios error after logging it
 */
export const getOperatorMetadata = async (dispatch: AppDispatch): Promise<void> => {
  const url = '/api/fetchOperatorMetadata';

  try {
    const response = await apiClient.get<OperatorsResponse>(url, { headers: BFF_HEADERS });

    logUtil.info({
      logger,
      message: 'Successfully fetched operator metadata',
      data: { operatorCount: Object.keys(response.data || {}).length },
    });

    dispatch(setOperatorMetadata(response.data));

  } catch (error) {
    // Log and absorb — never throw. An unhandled rejection here propagates out of
    // the `void fetchOperatorMetadata()` call in Canvas, triggers React's global
    // error handler in development, remounts the component, and creates an
    // infinite request loop.
    logUtil.error({
      logger,
      message: 'Failed to fetch operator metadata',
      data: error,
    });
  }
};

/**
 * Enrich a flow pipeline with per-node input/output feature metadata.
 *
 * Generic transport layer — knows nothing about pipeline shape or operator type.
 * Pass a type parameter `T` to get a fully typed response body; defaults to
 * `object` for callers that do not need to inspect the response.
 *
 * BFF endpoint:   POST /api/enrichFlowFeatures
 * Python backend: POST /api/v1/validation/enrich_flow_features
 *
 * @param pipelineFlow - Raw Elyra pipeline JSON
 * @returns Typed Axios response containing the enriched pipeline
 */
export const enrichFlowFeatures = async <T = object>(
  pipelineFlow: object
): Promise<AxiosResponse<T>> => {
  const url = '/api/enrichFlowFeatures';

  try {
    const response = await apiClient.post<T>(url, pipelineFlow, { headers: BFF_HEADERS });

    logUtil.info({
      logger,
      message: 'Successfully enriched flow features',
    });

    return response;

  } catch (error) {
    logUtil.error({
      logger,
      message: 'Failed to enrich flow features',
      data: error,
    });
    throw error;
  }
};

/**
 * Fetches available models for a given LLM/embedding provider from the BFF.
 *
 * @remarks
 * BFF endpoint: `GET /api/providers/:provider/models`
 * Python backend: `GET /api/v1/providers/{provider}/models`
 *
 * @param provider - One of `"ollama"`, `"watsonx"`, `"litellm"`
 * @param options - Optional `api_base` forwarded as query params
 * @returns The `ModelsResponse` containing the provider name and list of models
 */
export const getProviderModels = async (
  provider: string,
  options?: { api_base?: string }
): Promise<ModelsResponse> => {
  const params = new URLSearchParams();
  if (options?.api_base) {params.append('api_base', options.api_base);}

  const query = params.toString() ? `?${params.toString()}` : '';
  const url = `/api/providers/${provider}/models${query}`;

  try {
    const response = await apiClient.get<ModelsResponse>(url, { headers: BFF_HEADERS });

    logUtil.info({
      logger,
      message: 'Successfully fetched provider models',
      data: { provider, modelCount: response.data.models?.length ?? 0 },
    });

    return response.data;

  } catch (error) {
    logUtil.error({
      logger,
      message: 'Failed to fetch provider models',
      data: { provider, error },
    });
    throw error;
  }
};
