import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useRecentlyVisited } from '@/hooks/useRecentlyVisited';
import type { RecentItem } from '@/hooks/useRecentlyVisited';

const item1: RecentItem = { id: 'p-1', label: 'Project 1', path: '/projects/p-1', type: 'project' };
const item2: RecentItem = { id: 'p-2', label: 'Project 2', path: '/projects/p-2', type: 'project' };

beforeEach(() => {
  localStorage.clear();
});

describe('useRecentlyVisited', () => {
  it('reads from localStorage on init', () => {
    localStorage.setItem('docpipe.recentlyVisited', JSON.stringify([item1]));
    const { result } = renderHook(() => useRecentlyVisited());
    expect(result.current.recent).toHaveLength(1);
    expect(result.current.recent[0]?.id).toBe('p-1');
  });

  it('addEntry prepends to list', () => {
    const { result } = renderHook(() => useRecentlyVisited());
    act(() => { result.current.addEntry(item1); });
    act(() => { result.current.addEntry(item2); });
    expect(result.current.recent[0]?.id).toBe('p-2');
    expect(result.current.recent[1]?.id).toBe('p-1');
  });

  it('addEntry deduplicates by id — moves existing to front', () => {
    const { result } = renderHook(() => useRecentlyVisited());
    act(() => { result.current.addEntry(item1); });
    act(() => { result.current.addEntry(item2); });
    act(() => { result.current.addEntry(item1); }); // re-add item1
    expect(result.current.recent[0]?.id).toBe('p-1');
    expect(result.current.recent).toHaveLength(2);
  });

  it('addEntry caps at MAX_CAPACITY (10)', () => {
    const { result } = renderHook(() => useRecentlyVisited());
    for (let i = 0; i < 12; i++) {
      act(() => {
        result.current.addEntry({ id: `item-${i}`, label: `Item ${i}`, path: `/p/${i}`, type: 'project' });
      });
    }
    expect(result.current.recent).toHaveLength(10);
  });

  it('clearAll empties list and persists to localStorage', () => {
    const { result } = renderHook(() => useRecentlyVisited());
    act(() => { result.current.addEntry(item1); });
    act(() => { result.current.clearAll(); });
    expect(result.current.recent).toHaveLength(0);
    expect(localStorage.getItem('docpipe.recentlyVisited')).toBe('[]');
  });
});
