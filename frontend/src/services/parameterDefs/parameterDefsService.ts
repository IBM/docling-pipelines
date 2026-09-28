/**
 * Fetches operator parameter definitions for a given operator.
 * Defaults are applied to the canvas model by applyNodeDefaults (Canvas.tsx) on drop
 * and are available in node.parameters by the time the panel opens via current_parameters.
 */

import type { ParameterDef } from '@/types/parameterDef';
import { log4js, logUtil } from '@/utils/logger';

const logger = log4js.getLogger('ParameterDefsService');

/** Minimal paramDef returned when no operator-specific file exists. */
const FALLBACK_PARAM_DEF: ParameterDef = {
  parameters: [],
  uihints: {
    group_info: [{ id: 'common_properties_panel', type: 'customPanel' }],
  },
};

/**
 * Fetches the raw parameter definition for an operator from the public assets.
 * The panel reads saved values from node.parameters via current_parameters —
 * no default-stamping into the paramDef is required.
 *
 * @param operatorName - Operator short name (e.g. 'vectordb', 'embeddings')
 */
export const getParameterDef = async ({
  operatorName,
}: {
  operatorName: string;
}): Promise<ParameterDef> => {
  const url = `/ui/parameterDefs/${operatorName}_paramDef.json`;

  try {
    const response = await fetch(url, {
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache,no-store',
      },
      method: 'GET',
      mode: 'cors',
      credentials: 'include',
    });

    if (!response.ok) {
      logUtil.warn({
        logger,
        message: 'Parameter definition not found, using fallback',
        data: { operatorName, status: response.status },
      });
      return FALLBACK_PARAM_DEF;
    }

    const paramDef = (await response.json()) as ParameterDef;

    logUtil.info({
      logger,
      message: 'Parameter definition loaded',
      data: { operatorName },
    });

    return paramDef;
  } catch (error) {
    logUtil.error({
      logger,
      message: 'Failed to fetch parameter definition, using fallback',
      data: { operatorName, error },
    });
    return FALLBACK_PARAM_DEF;
  }
};
