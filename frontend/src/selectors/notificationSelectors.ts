/**
 * @fileoverview Selectors for accessing notifications state from the Redux store.
 * All selectors read from `state.notifications`, owned by `notificationsSlice`.
 */

import type { RootState } from '@/store';
import type { Notification, NotificationPreferences } from '@/types/notifications';

/** Active toasts currently rendered by `ToastContainer`. */
export const selectActiveNotifications = (state: RootState): Notification[] =>
  state.notifications.active;

/** Append-only history of all notifications shown this session. */
export const selectNotificationHistory = (state: RootState): Notification[] =>
  state.notifications.history;

/** Number of notifications added since the history panel was last opened. */
export const selectNotificationUnreadCount = (state: RootState): number =>
  state.notifications.unreadCount;

/** User-configurable notification display preferences. */
export const selectNotificationPreferences = (state: RootState): NotificationPreferences =>
  state.notifications.preferences;
