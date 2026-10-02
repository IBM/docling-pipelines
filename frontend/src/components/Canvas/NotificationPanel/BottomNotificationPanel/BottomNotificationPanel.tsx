/*
 * Licensed Materials - Property of IBM
 * © Copyright IBM Corp. 2024, 2026.
 */

import React, { useState } from 'react';
import { Button, CopyButton } from '@carbon/react';
import { Close, WarningAlt, ErrorFilled, ChevronRight, ChevronDown } from '@carbon/react/icons';
import { SharedDataTable } from '@/components/common/SharedDataTable';
import type { SharedDataTableHeader, SharedDataTableRow } from '@/components/common/SharedDataTable';
import styles from './BottomNotificationPanel.module.scss';
import {
  COLUMN_KEYS,
  COLUMN_HEADERS,
  NOTIFICATION_TYPES,
  DEFAULT_VALUES,
  ARIA_LABELS,
  BUTTON_TITLES,
} from '@/constants/notificationPanel';

import type { ValidationActionType } from '@/services/api';

export interface NotificationItem {
  id: string;
  type: 'error' | 'warning';
  code: string | null;
  message: string | null;
  node_name?: string | null;
  node_id?: string | null;
  message_code?: string | null;
  action_type?: ValidationActionType | null;
  timestamp: string;
}

interface BottomNotificationPanelProps {
  notifications: NotificationItem[];
  onClose: () => void;
  title?: string;
  onNodeClick?: (nodeId: string, messageCode?: string | null, actionType?: ValidationActionType | null) => void;
}

const HEADERS: SharedDataTableHeader[] = [
  { key: COLUMN_KEYS.EXPAND,      header: COLUMN_HEADERS.EXPAND },
  { key: COLUMN_KEYS.NUMBER,      header: COLUMN_HEADERS.NUMBER },
  { key: COLUMN_KEYS.TIMESTAMP,   header: COLUMN_HEADERS.TIMESTAMP },
  { key: COLUMN_KEYS.STATUS,      header: COLUMN_HEADERS.STATUS },
  { key: COLUMN_KEYS.NAME,        header: COLUMN_HEADERS.NAME },
  { key: COLUMN_KEYS.DESCRIPTION, header: COLUMN_HEADERS.DESCRIPTION },
];

/**
 * BottomNotificationPanel
 *
 * Displays validation errors and warnings using SharedDataTable.
 * Expanded rows are injected immediately after their parent row via
 * `renderRowExtras`, which SharedDataTable places inside the same <tbody>
 * as a React.Fragment sibling — keeping the correct DOM order regardless
 * of pagination.
 */
const BottomNotificationPanel: React.FC<BottomNotificationPanelProps> = ({
  notifications,
  onClose,
  title = DEFAULT_VALUES.TITLE,
  onNodeClick,
}) => {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const toggleRow = (rowId: string): void => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(rowId)) { next.delete(rowId); } else { next.add(rowId); }
      return next;
    });
  };

  const handleCopy = (text: string): void => {
    void navigator.clipboard.writeText(text).catch(() => { /* clipboard denied */ });
  };

  // ── Row data ──────────────────────────────────────────────────────────────

  const rows: SharedDataTableRow[] = notifications.map((notif, index) => {
    const rawMessage = notif.message ?? '';
    const truncatedMessage = rawMessage.length > 100
      ? `${rawMessage.slice(0, 100)}...`
      : rawMessage;

    return {
      id: notif.id,
      [COLUMN_KEYS.EXPAND]:      '',
      [COLUMN_KEYS.NUMBER]:      (index + 1).toString(),
      [COLUMN_KEYS.TIMESTAMP]:   notif.timestamp,
      [COLUMN_KEYS.STATUS]:      notif.type,
      [COLUMN_KEYS.NAME]:        notif.node_name ?? DEFAULT_VALUES.NODE_NAME_PLACEHOLDER,
      [COLUMN_KEYS.DESCRIPTION]: truncatedMessage,
    };
  });

  // ── Cell renderer ─────────────────────────────────────────────────────────

  const renderCell = (
    cell: { id: string; value: React.ReactNode; info: { header: string } },
    row: SharedDataTableRow
  ): React.ReactNode => {
    const notification = notifications.find((n) => n.id === row.id);
    const colKey = cell.info.header;

    if (colKey === COLUMN_KEYS.EXPAND) {
      const isExpanded = expandedRows.has(row.id);
      return (
        <button
          type="button"
          className={styles.expandIcon}
          onClick={() => { toggleRow(row.id); }}
          aria-label={isExpanded ? ARIA_LABELS.COLLAPSE_ROW : ARIA_LABELS.EXPAND_ROW}
        >
          {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </button>
      );
    }

    if (colKey === COLUMN_KEYS.STATUS) {
      return (cell.value as string) === NOTIFICATION_TYPES.ERROR
        ? <ErrorFilled className={styles.errorIcon} />
        : <WarningAlt className={styles.warningIcon} />;
    }

    if (colKey === COLUMN_KEYS.NAME) {
      const nodeId = notification?.node_id;
      const messageCode = notification?.message_code;
      const actionType = notification?.action_type;
      const isNavigable = actionType !== 'none';
      if (nodeId && onNodeClick && isNavigable) {
        return (
          <button
            type="button"
            className={styles.nodeLink}
            onClick={() => { onNodeClick(nodeId, messageCode, actionType); }}
          >
            {cell.value}
          </button>
        );
      }
      return cell.value;
    }

    if (colKey === COLUMN_KEYS.DESCRIPTION) {
      const fullMessage = notification?.message ?? String(cell.value ?? '');
      return (
        <div className={styles.descriptionCell}>
          <span className={styles.descriptionText}>{cell.value}</span>
          <CopyButton
            className={styles.copyButton}
            onClick={() => { handleCopy(fullMessage); }}
            iconDescription={BUTTON_TITLES.COPY_TO_CLIPBOARD}
            feedback="Copied"
            feedbackTimeout={2000}
            align="left"
          />
        </div>
      );
    }

    return undefined;
  };

  // ── Expanded row — injected inline after the data row via renderRowExtras ──

  const renderRowExtras = (row: SharedDataTableRow): React.ReactNode => {
    if (!expandedRows.has(row.id)) { return null; }
    const notification = notifications.find((n) => n.id === row.id);
    if (!notification) { return null; }
    return (
      <tr className={styles.expandedRow}>
        <td colSpan={HEADERS.length} className={styles.expandedCell}>
          <span className={styles.expandedContent}>{notification.message}</span>
        </td>
      </tr>
    );
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className={styles.bottomPanel}>
      <div className={styles.header}>
        <h3 className={styles.title}>{title}</h3>
        <div className={styles.actions}>
          <Button
            kind="ghost"
            size="sm"
            hasIconOnly
            renderIcon={Close}
            iconDescription={ARIA_LABELS.CLOSE}
            onClick={onClose}
          />
        </div>
      </div>
      <div className={styles.tableContainer}>
        <SharedDataTable
          headers={HEADERS}
          rows={rows}
          searchable
          searchPlaceholder={DEFAULT_VALUES.SEARCH_PLACEHOLDER}
          size="sm"
          renderCell={renderCell}
          renderRowExtras={renderRowExtras}
        />
      </div>
    </div>
  );
};

export default BottomNotificationPanel;
