import { describe, it, expect } from 'vitest';
import notificationsReducer, {
  addNotification,
  removeNotification,
  clearActiveNotifications,
  clearHistory,
  markHistoryRead,
} from '@/slices/notificationsSlice';
import type { NotificationsState } from '@/types/notifications';

const initialState: NotificationsState = {
  active: [],
  history: [],
  preferences: { autoDismiss: true, dismissDelay: 5000 },
  unreadCount: 0,
};

describe('notificationsSlice reducers', () => {
  it('initial state is correct', () => {
    const state = notificationsReducer(undefined, { type: '@@INIT' });
    expect(state.active).toEqual([]);
    expect(state.history).toEqual([]);
    expect(state.unreadCount).toBe(0);
  });

  it('addNotification appends to active and history, increments unreadCount', () => {
    const state = notificationsReducer(initialState, addNotification({
      kind: 'success',
      title: 'Flow saved',
    }));
    expect(state.active).toHaveLength(1);
    expect(state.history).toHaveLength(1);
    expect(state.unreadCount).toBe(1);
    expect(state.active[0]?.title).toBe('Flow saved');
    expect(state.active[0]?.kind).toBe('success');
  });

  it('addNotification generates an id automatically', () => {
    const state = notificationsReducer(initialState, addNotification({
      kind: 'info',
      title: 'Test',
    }));
    expect(state.active[0]?.id).toBeTruthy();
  });

  it('removeNotification removes from active by id', () => {
    const stateWithOne = notificationsReducer(initialState, addNotification({ kind: 'error', title: 'Err' }));
    const id = stateWithOne.active[0]!.id;
    const state = notificationsReducer(stateWithOne, removeNotification(id));
    expect(state.active).toHaveLength(0);
    // history is preserved
    expect(state.history).toHaveLength(1);
  });

  it('clearActiveNotifications empties active, preserves history', () => {
    const stateWithOne = notificationsReducer(initialState, addNotification({ kind: 'info', title: 'A' }));
    const state = notificationsReducer(stateWithOne, clearActiveNotifications());
    expect(state.active).toHaveLength(0);
    expect(state.history).toHaveLength(1);
  });

  it('clearHistory empties history and resets unreadCount', () => {
    const stateWithOne = notificationsReducer(initialState, addNotification({ kind: 'info', title: 'A' }));
    const state = notificationsReducer(stateWithOne, clearHistory());
    expect(state.history).toHaveLength(0);
    expect(state.unreadCount).toBe(0);
  });

  it('markHistoryRead resets unreadCount to 0', () => {
    const stateWithSome = notificationsReducer(
      notificationsReducer(initialState, addNotification({ kind: 'info', title: 'A' })),
      addNotification({ kind: 'success', title: 'B' })
    );
    expect(stateWithSome.unreadCount).toBe(2);
    const state = notificationsReducer(stateWithSome, markHistoryRead());
    expect(state.unreadCount).toBe(0);
  });
});
