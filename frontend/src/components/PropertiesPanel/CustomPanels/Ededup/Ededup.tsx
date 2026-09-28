/**
 * @file De-duplicator operator configuration panel body.
 *
 * The `ededup` operator has no user-configurable attributes — it automatically
 * removes exact duplicate documents based on a content hash. This panel renders
 * an informational message explaining that behaviour.
 */

import React from 'react';
import { InlineNotification } from '@carbon/react';

interface EdedupPanelBodyProps {
  controller: any;
}

// controller is required by the OPERATOR_PANEL_MAP signature but unused here

export function EdedupPanelBody({ controller: _controller }: EdedupPanelBodyProps): React.JSX.Element {
  return (
    <InlineNotification
      kind="info"
      title="No configuration required"
      subtitle="This operator automatically removes exact duplicate documents based on a content hash. No parameters need to be set."
      lowContrast
      hideCloseButton
    />
  );
}
