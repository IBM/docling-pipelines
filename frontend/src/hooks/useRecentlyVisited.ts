// TODO: This entire hook is a localStorage-only stub.
// Once the API is available, replace with a call to the recently-visited endpoint
// (e.g. GET /api/v1/users/me/recently-visited) and remove the localStorage read/write logic.

import { useState, useCallback } from 'react';

/** Maximum number of items retained in the recently-visited list. */
const MAX_CAPACITY = 10;

/** localStorage key used to persist the recently-visited list. */
const STORAGE_KEY = 'docpipe.recentlyVisited';

/** Type of entity that can appear in the recently-visited list. */
export type RecentItemType = 'project' | 'flow' | 'run';

/** A single entry in the recently-visited list. */
export interface RecentItem {
  /** Unique identifier for the entity (e.g. project or flow ID). */
  id: string;
  /** Human-readable display label shown in the recently-visited UI. */
  label: string;
  /** Absolute path the item navigates to (e.g. `/projects/proj-1`). */
  path: string;
  /** Category of the entity. */
  type: RecentItemType;
}

/** Return shape of {@link useRecentlyVisited}. */
interface UseRecentlyVisitedReturn {
  /** Ordered list of recently visited items, most recent first. */
  recent: RecentItem[];
  /**
   * Adds an entry to the front of the list (LRU — if the same `id` already
   * exists it is moved to the front rather than duplicated).
   */
  addEntry: (item: RecentItem) => void;
  /**
   * Removes a single entry by its `id`. No-ops if the id is not in the list.
   * Used to evict deleted projects/flows from the recently-visited bar.
   */
  removeEntry: (id: string) => void;
  /** Clears all entries from memory and localStorage. */
  clearAll: () => void;
}

/** Reads the persisted list from localStorage, returning `[]` on any error. */
function readFromStorage(): RecentItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) { return []; }
    return JSON.parse(raw) as RecentItem[];
  } catch {
    return [];
  }
}

/** Writes the list to localStorage, degrading silently on quota/private-browsing errors. */
function writeToStorage(items: RecentItem[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  } catch {
    // Quota exceeded or private-browsing restriction — degrade silently
  }
}

/**
 * Manages a capped, ordered recently-visited list backed by localStorage.
 *
 * - State is initialised from localStorage on first render.
 * - All mutations (`addEntry`, `removeEntry`, `clearAll`) are written back
 *   to localStorage synchronously after each update.
 * - Maximum capacity is {@link MAX_CAPACITY} items (LRU eviction).
 * - Storage key: `docpipe.recentlyVisited` — one JSON array per browser origin.
 *
 * @returns `{ recent, addEntry, removeEntry, clearAll }`
 */
export function useRecentlyVisited(): UseRecentlyVisitedReturn {
  const [recent, setRecent] = useState<RecentItem[]>(readFromStorage);

  const addEntry = useCallback((item: RecentItem) => {
    setRecent((prev) => {
      // Remove existing entry with same id to bring it to front (LRU)
      const filtered = prev.filter((r) => r.id !== item.id);
      // Prepend and enforce capacity
      const next = [item, ...filtered].slice(0, MAX_CAPACITY);
      writeToStorage(next);
      return next;
    });
  }, []);

  const removeEntry = useCallback((id: string) => {
    setRecent((prev) => {
      const next = prev.filter((r) => r.id !== id);
      writeToStorage(next);
      return next;
    });
  }, []);

  const clearAll = useCallback(() => {
    writeToStorage([]);
    setRecent([]);
  }, []);

  return { recent, addEntry, removeEntry, clearAll };
}
