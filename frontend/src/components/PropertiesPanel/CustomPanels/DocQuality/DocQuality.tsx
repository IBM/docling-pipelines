/**
 * @file DocQuality properties panel body.
 *
 * The `doc_quality` operator has no user-configurable attributes.
 */

import React from 'react';
import { InlineNotification } from '@carbon/react';

interface DocQualityPanelBodyProps {
  controller: any;
}

export function DocQualityPanelBody({ controller: _controller }: DocQualityPanelBodyProps): React.JSX.Element {
  return (
    <InlineNotification
      kind="info"
      title="No configuration required"
      subtitle="This operator automatically computes document quality metrics. No parameters need to be set."
      lowContrast
      hideCloseButton
    />
  );
}
