import React from 'react';
import { render, type RenderOptions } from '@testing-library/react';
import { Provider } from 'react-redux';
import { MemoryRouter } from 'react-router-dom';
import { IntlProvider } from 'react-intl';
import { ThemeProvider } from '@/contexts';
import { createTestStore, buildPreloadedState } from '../mocks/fixtures/store.fixture';
import type { RootState } from '@/store';

interface RenderWithProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  preloadedState?: Partial<RootState>;
  initialEntries?: string[];
}

/**
 * Wraps `render()` with all required context providers:
 * - Redux store (real configureStore, optional preloadedState)
 * - MemoryRouter (React Router)
 * - IntlProvider (react-intl, en locale)
 * - ThemeProvider (Carbon theme context)
 *
 * Use this in all component tests instead of bare `render`.
 */
export function renderWithProviders(
  ui: React.ReactElement,
  {
    preloadedState,
    initialEntries = ['/'],
    ...renderOptions
  }: RenderWithProvidersOptions = {}
) {
  const store = createTestStore(buildPreloadedState(preloadedState));

  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <Provider store={store}>
        <MemoryRouter initialEntries={initialEntries}>
          <IntlProvider locale="en" defaultLocale="en">
            <ThemeProvider>{children}</ThemeProvider>
          </IntlProvider>
        </MemoryRouter>
      </Provider>
    );
  }

  return { store, ...render(ui, { wrapper: Wrapper, ...renderOptions }) };
}
