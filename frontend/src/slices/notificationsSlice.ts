/**
 * @fileoverview Redux slice for the global notification system.
 *
 * Mirrors the three-tier pattern used in the reference repo:
 *   - Global toasts  → `addNotification` dispatched from `useNotify()` hook
 *   - Canvas toasts  → same hook, called after save/run
 *   - Inline notices → `@carbon/react` `InlineNotification` in component JSX (not this slice)
 *
 * State shape:
 *   - `active`      — toasts currently visible in `ToastContainer`
 *   - `history`     — append-only log of every notification shown this session
 *   - `preferences` — auto-dismiss toggle + delay (future preferences UI hooks here)
 *   - `unreadCount` — badge counter on the history bell icon
 */

import { createSlice, type PayloadAction } from '@reduxjs/toolkit';
import type {
  NotificationsState,
  Notification,
  NotificationKind,
  NotificationPreferences,
} from '@/types/notifications';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function generateId(): string {
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

// ─── Initial state ────────────────────────────────────────────────────────────

const initialState: NotificationsState = {
  active: [],
  history: [],
  preferences: {
    autoDismiss: true,
    dismissDelay: 5000,
  },
  unreadCount: 0,
};

// ─── Payload types ────────────────────────────────────────────────────────────

/** Caller-supplied fields when dispatching a new notification. */
export interface AddNotificationPayload {
  kind: NotificationKind;
  title: string;
  subtitle?: string;
  caption?: string;
  /** Override the slice-level auto-dismiss delay for this notification only. */
  dismissAfter?: number;
}

// ─── Slice ────────────────────────────────────────────────────────────────────

const notificationsSlice = createSlice({
  name: 'notifications',
  initialState,
  reducers: {
    /**
     * Adds a new notification to both `active` (shown as a toast) and
     * `history` (persisted in the history panel). Increments `unreadCount`.
     *
     * The slice assigns `id` and `timestamp` — callers never provide them.
     */
    addNotification: (state, action: PayloadAction<AddNotificationPayload>) => {
      const entry: Notification = {
        id: generateId(),
        timestamp: new Date().toISOString(),
        ...action.payload,
      };
      state.active.push(entry);
      state.history.unshift(entry); // newest first in the history panel
      state.unreadCount += 1;
    },

    /**
     * Removes a single toast from `active` by ID.
     * The entry stays in `history` — dismissing a toast does not erase history.
     */
    removeNotification: (state, action: PayloadAction<string>) => {
      state.active = state.active.filter((n) => n.id !== action.payload);
    },

    /** Clears all active toasts (e.g. navigating away). History is preserved. */
    clearActiveNotifications: (state) => {
      state.active = [];
    },

    /** Clears the full notification history and resets the unread counter. */
    clearHistory: (state) => {
      state.history = [];
      state.unreadCount = 0;
    },

    /**
     * Resets the unread counter to zero.
     * Dispatched when the user opens the history panel.
     */
    markHistoryRead: (state) => {
      state.unreadCount = 0;
    },

    /**
     * Updates notification preferences.
     * Partial update — only provided keys are changed.
     */
    setPreferences: (state, action: PayloadAction<Partial<NotificationPreferences>>) => {
      state.preferences = { ...state.preferences, ...action.payload };
    },
  },
});

export const {
  addNotification,
  removeNotification,
  clearActiveNotifications,
  clearHistory,
  markHistoryRead,
  setPreferences,
} = notificationsSlice.actions;

export default notificationsSlice.reducer;
