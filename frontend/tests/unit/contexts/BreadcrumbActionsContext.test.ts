import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import React, { useState } from 'react';
import { BreadcrumbActionsContext, useBreadcrumbActions } from '@/contexts/BreadcrumbActionsContext';

function makeWrapper() {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    const [actions, setActions] = useState<React.ReactNode>(null);
    return React.createElement(
      BreadcrumbActionsContext.Provider,
      { value: { actions, setActions } },
      children
    );
  };
}

describe('useBreadcrumbActions', () => {
  it('inside provider returns { actions, setActions }', () => {
    const { result } = renderHook(() => useBreadcrumbActions(), { wrapper: makeWrapper() });
    expect(result.current.actions).toBeNull();
    expect(typeof result.current.setActions).toBe('function');
  });

  it('setActions updates actions to a new node value', () => {
    const { result } = renderHook(() => useBreadcrumbActions(), { wrapper: makeWrapper() });
    const node = React.createElement('span', null, 'Edit');
    act(() => {
      result.current.setActions(node);
    });
    expect(result.current.actions).toBe(node);
  });

  it('setActions(null) sets actions to null', () => {
    const { result } = renderHook(() => useBreadcrumbActions(), { wrapper: makeWrapper() });
    act(() => { result.current.setActions(React.createElement('span', null, 'X')); });
    act(() => { result.current.setActions(null); });
    expect(result.current.actions).toBeNull();
  });
});
