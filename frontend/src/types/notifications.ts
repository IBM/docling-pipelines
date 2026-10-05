/**
 * @fileoverview Type definitions for the global notification system.
 *
 * Three-tier notification architecture:
 * 1. Global toasts   — dispatched via `useNotify()` hook; rendered by `ToastContainer`
 * 2. Canvas toasts   — same hook, same slice; Canvas calls notify after save/run
 * 3. Inline          — `@carbon/react` `InlineNotification` rendered directly in
 *                      component JSX for contextual form errors (unchanged)
 */

/** Notification severity — maps directly to Carbon `ToastNotification` `kind` prop. */
export type NotificationKind = 'success' | 'error' | 'warning' | 'info';

/** A single notification entry stored in the Redux slice. */
export interface Notification {
  /** Unique identifier — `crypto.randomUUID()` assigned by the slice. */
  id: string;
  /** Visual severity and icon. */
  kind: NotificationKind;
  /** Short heading shown in bold. */
  title: string;
  /** Optional detail sentence below the title. */
  subtitle?: string;
  /** Optional context line — e.g. timestamp or transaction ID. */
  caption?: string;
  /**
   * Auto-dismiss delay in milliseconds.
   * `0` means sticky — the user must dismiss manually.
   * Defaults to the slice-level `preferences.dismissDelay`.
   */
  dismissAfter?: number;
  /** ISO timestamp set when the notification is created. Used in the history panel. */
  timestamp: string;
}

/**
 * User-configurable notification preferences.
 * Stored in the Redux slice; a preferences UI can dispatch `setPreferences`
 * to update these values when that feature is built.
 */
export interface NotificationPreferences {
  /**
   * When `true` toasts auto-dismiss after `dismissDelay` ms.
   * When `false` all toasts are sticky.
   */
  autoDismiss: boolean;
  /** Auto-dismiss duration in milliseconds (default: 5000). */
  dismissDelay: number;
}

/** Shape of `state.notifications` in the Redux store. */
export interface NotificationsState {
  /** Active toasts currently rendered by `ToastContainer`. */
  active: Notification[];
  /**
   * Append-only history of all notifications ever shown this session.
   * Survives individual dismissals — accessible from the history panel.
   */
  history: Notification[];
  /** Configurable display preferences. */
  preferences: NotificationPreferences;
  /** Number of notifications added since the history panel was last opened. */
  unreadCount: number;
}
