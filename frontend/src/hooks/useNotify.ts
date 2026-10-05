/**
 * @fileoverview `useNotify` — the primary API for dispatching global notifications.
 *
 * Dispatches toast notifications via Redux. Use this instead of calling
 * `addNotification` directly from component code.
 *
 * Usage:
 * ```ts
 * const notify = useNotify();
 * notify.success('Flow saved');
 * notify.error('Failed to delete run', { subtitle: error.message });
 * notify.warning('Flow has validation warnings');
 * notify.info('Job is queued');
 * ```
 */

import { useCallback } from 'react';
import { useAppDispatch } from '@/hooks/useAppDispatch';
import { addNotification } from '@/slices/notificationsSlice';
import type { NotificationKind } from '@/types/notifications';
import type { AddNotificationPayload } from '@/slices/notificationsSlice';

type NotifyOptions = Omit<AddNotificationPayload, 'kind' | 'title'>;

interface NotifyFn {
  (title: string, options?: NotifyOptions): void;
}

interface UseNotifyReturn {
  /** Show a green success toast. */
  success: NotifyFn;
  /** Show a red error toast. Auto-dismiss is disabled for errors (sticky by default). */
  error: NotifyFn;
  /** Show a yellow warning toast. */
  warning: NotifyFn;
  /** Show a blue informational toast. */
  info: NotifyFn;
  /** Low-level method — use the typed helpers above when possible. */
  notify: (kind: NotificationKind, title: string, options?: NotifyOptions) => void;
}

/**
 * Returns a stable set of notification dispatch helpers.
 *
 * Error notifications default to sticky (`dismissAfter: 0`) so the user must
 * acknowledge them. All other kinds auto-dismiss using the slice preference
 * (`dismissDelay`, default 5000 ms).
 *
 * The returned object is referentially stable across renders.
 */
export function useNotify(): UseNotifyReturn {
  const dispatch = useAppDispatch();

  const notify = useCallback(
    (kind: NotificationKind, title: string, options: NotifyOptions = {}): void => {
      dispatch(addNotification({ kind, title, ...options }));
    },
    [dispatch]
  );

  const success = useCallback(
    (title: string, options: NotifyOptions = {}): void => { notify('success', title, options); },
    [notify]
  );

  const error = useCallback(
    (title: string, options: NotifyOptions = {}): void => {
      // Errors are sticky by default — callers can override with dismissAfter > 0.
      notify('error', title, { dismissAfter: 0, ...options });
    },
    [notify]
  );

  const warning = useCallback(
    (title: string, options: NotifyOptions = {}): void => { notify('warning', title, options); },
    [notify]
  );

  const info = useCallback(
    (title: string, options: NotifyOptions = {}): void => { notify('info', title, options); },
    [notify]
  );

  return { success, error, warning, info, notify };
}
