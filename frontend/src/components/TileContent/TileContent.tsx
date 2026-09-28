import React from 'react';
import { Button } from '@carbon/react';
import { ArrowRight } from '@carbon/icons-react';
import styles from './TileContent.module.scss';

interface TileContentProps {
  label: string;
  title: string;
  subtitle: string;
  buttonLabel: string;
  href?: string;
  onAction?: () => void;
}

/** Figma glass tile body: label / title / subtitle / tertiary CTA button */
export function TileContent({
  label,
  title,
  subtitle,
  buttonLabel,
  href,
  onAction,
}: TileContentProps): React.JSX.Element {
  return (
    <div className={styles.tileContent}>
      <span className={styles.tileLabel}>{label}</span>
      <p className={styles.tileTitle}>{title}</p>
      <p className={styles.tileSubtitle}>{subtitle}</p>
      <div className={styles.tileAction}>
        {href ? (
          <Button
            kind="tertiary"
            size="sm"
            renderIcon={ArrowRight}
            href={href}
            target="_blank"
            rel="noopener noreferrer"
          >
            {buttonLabel}
          </Button>
        ) : (
          <Button
            kind="tertiary"
            size="sm"
            renderIcon={ArrowRight}
            onClick={() => { onAction?.(); }}
          >
            {buttonLabel}
          </Button>
        )}
      </div>
    </div>
  );
}
