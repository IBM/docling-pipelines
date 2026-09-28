import React from 'react';
import { Tearsheet, TearsheetNarrow } from '@carbon/ibm-products';
import { useThemeElement } from '@/contexts';

export interface SharedTearsheetProps {
  open: boolean;
  onClose: () => void;
  title: React.ReactNode;
  label?: string;
  children: React.ReactNode;
  /**
   * 'lg' renders a wide Tearsheet (slide-in from the right, full height).
   * 'xs' | 'sm' | 'md' render a TearsheetNarrow (narrower variant).
   * Defaults to 'lg'.
   */
  size?: 'xs' | 'sm' | 'md' | 'lg';
  /**
   * Not forwarded — ibm-products Tearsheet is always dismissible via the close icon.
   * Kept in the interface for API compatibility with existing callers.
   */
  preventCloseOnClickOutside?: boolean;
  primaryActionLabel?: string;
  secondaryActionLabel?: string;
  onPrimaryAction?: () => void;
  onSecondaryAction?: () => void;
  hideFooter?: boolean;
  className?: string;
}

export function SharedTearsheet({
  open,
  onClose,
  title,
  label,
  children,
  size = 'lg',
  preventCloseOnClickOutside: _preventCloseOnClickOutside,
  primaryActionLabel,
  secondaryActionLabel = 'Close',
  onPrimaryAction,
  onSecondaryAction,
  hideFooter = false,
  className,
}: SharedTearsheetProps): React.JSX.Element {
  // The ibm-products Tearsheet portals to document.body by default, which is
  // outside the Carbon <Theme> wrapper and loses all CSS custom-property
  // overrides.  portalTarget redirects the portal into the theme element so
  // CSS variable inheritance (--cds-layer-01, --cds-background, etc.) works.
  const portalTarget = useThemeElement();

  // Build the ibm-products `actions` array from the legacy primary/secondary props.
  // When hideFooter is true no action buttons are shown (passive tearsheet).
  const actions = hideFooter
    ? undefined
    : [
        ...(primaryActionLabel && onPrimaryAction
          ? [{ label: primaryActionLabel, kind: 'primary' as const, onClick: onPrimaryAction }]
          : []),
        {
          label: secondaryActionLabel,
          kind: 'secondary' as const,
          onClick: onSecondaryAction ?? onClose,
        },
      ];

  if (size !== 'lg') {
    return (
      <TearsheetNarrow
        open={open}
        onClose={onClose}
        title={title}
        label={label}
        actions={actions}
        hasCloseIcon
        closeIconDescription="Close"
        className={className}
        portalTarget={portalTarget}
      >
        {children}
      </TearsheetNarrow>
    );
  }

  return (
    <Tearsheet
      open={open}
      onClose={onClose}
      title={title}
      label={label}
      actions={actions}
      hasCloseIcon
      closeIconDescription="Close"
      className={className}
      portalTarget={portalTarget}
    >
      {children}
    </Tearsheet>
  );
}
