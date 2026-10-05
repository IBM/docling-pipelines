/*
 * Licensed Materials - Property of IBM
 * © Copyright IBM Corp. 2024, 2026.
 */

import React from 'react';
import { ErrorFilled, WarningAlt, Close } from '@carbon/react/icons';
import styles from './TopNotificationBar.module.scss';

interface TopNotificationBarProps {
  errorCount: number;
  warningCount: number;
  onViewClick: () => void;
  onClose: () => void;
}

const TopNotificationBar: React.FC<TopNotificationBarProps> = ({
  errorCount,
  warningCount,
  onViewClick,
  onClose,
}) => {
  const totalCount = errorCount + warningCount;

  if (totalCount === 0) {
    return null;
  }

  const hasOnlyWarnings = warningCount > 0 && errorCount === 0;

  const getMessage = (): string => {
    const parts: string[] = [];

    if (errorCount > 0) {
      parts.push(errorCount === 1 ? '1 validation error' : `${errorCount} validation errors`);
    }

    if (warningCount > 0) {
      parts.push(warningCount === 1 ? '1 warning' : `${warningCount} warnings`);
    }

    const allSingular = (errorCount === 0 || errorCount === 1) && (warningCount === 0 || warningCount === 1);
    const verb = allSingular ? 'there is' : 'there are';
    return `${verb} ${parts.join(' and ')}`;
  };

  const getTitle = (): string => (hasOnlyWarnings ? 'Validation warning' : 'Validation failed');

  const barClassName = hasOnlyWarnings
    ? `${styles.topNotificationBar} ${styles.warningBar}`
    : styles.topNotificationBar;

  return (
    <div className={barClassName}>
      <div className={styles.content}>
        {hasOnlyWarnings ? (
          <WarningAlt className={styles.warningIcon} />
        ) : (
          <ErrorFilled className={styles.errorIcon} />
        )}
        <span className={styles.title}>{getTitle()}</span>
        <span className={styles.message}>{getMessage()}</span>
      </div>
      <div className={styles.actions}>
        <button type="button" className={styles.viewLink} onClick={onViewClick}>
          View
        </button>
        <button
          type="button"
          className={styles.closeButton}
          onClick={onClose}
          aria-label="Close notification"
        >
          <Close size={16} />
        </button>
      </div>
    </div>
  );
};

export default TopNotificationBar;
