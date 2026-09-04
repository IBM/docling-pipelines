/**
 * @file DocQuality properties panel body.
 *
 * Renders the configuration UI for the `doc_quality` operator node.
 */

import React from 'react';
import { getRequiredParamValidator } from '@/utils/requiredParamValidation';
import { RequiredParamTooltip } from '@/components/common';
import { TextInput } from '@carbon/react';
import { NodeOperator } from '@/constants/operators';
import type { OperatorFeature, OperatorMetadata } from '@/types';
import common from '../../CommonPropertiesPanel.module.scss';

/** Attribute key for the `text_lang` parameter. */
const ATTR_TEXT_LANG = 'text_lang';

interface DocQualityPanelBodyProps {
  controller: any;
}

export function DocQualityPanelBody({ controller }: DocQualityPanelBodyProps): React.JSX.Element {
  // ── Read operator attribute metadata from Redux (passed in via Canvas.tsx) ──
  // eslint-disable-next-line @typescript-eslint/no-unsafe-call
  const operatorMetadata = (controller?.getAppData?.()?.operatorMetadata ?? {}) as Record<string, OperatorMetadata>;
  const nodeAttributes: Record<string, OperatorFeature> = operatorMetadata[NodeOperator.DOC_QUALITY]?.attributes ?? {};

  // ── Read current saved value, falling back to backend default ────────────
  const textLang: string =
    // eslint-disable-next-line @typescript-eslint/no-unsafe-call
    (controller?.getPropertyValue?.({ name: ATTR_TEXT_LANG }) as string | undefined)
    ?? (nodeAttributes[ATTR_TEXT_LANG]?.default as string | undefined)
    ?? 'en';

  // ── Required param validation ─────────────────────────────────────────────
  const validate = getRequiredParamValidator(nodeAttributes);
  const textLangValidation = validate(ATTR_TEXT_LANG, textLang);

  return (
    <div className={common.commonPropertiesPanelBody}>

      {/* ── Language ─────────────────────────────────────────────────── */}
      <div className={common.formField}>
        <div className={common.labelWithTooltip}>
          <RequiredParamTooltip
            paramId={ATTR_TEXT_LANG}
            nodeAttributes={nodeAttributes}
            definition={
              nodeAttributes[ATTR_TEXT_LANG]?.description
              ?? 'Language code for profanity detection. Affects docq_contain_bad_word accuracy.'
            }
          >
            Language
          </RequiredParamTooltip>
        </div>
        <TextInput
          id="text_lang"
          labelText="Language"
          hideLabel
          placeholder="en"
          value={textLang}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
            // eslint-disable-next-line @typescript-eslint/no-unsafe-call
            controller?.updatePropertyValue?.({ name: ATTR_TEXT_LANG }, e.target.value);
          }}
          invalid={textLangValidation.isInvalid}
          invalidText={textLangValidation.errorMessage}
        />
      </div>

    </div>
  );
}
