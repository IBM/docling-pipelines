import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Home } from '@carbon/icons-react';
import { ErrorEmptyState, NotFoundEmptyState } from '@carbon/ibm-products';
import { PageLayout } from '@/components';
import { ROUTES } from '@/config';
import { useTheme } from '@/hooks';
import styles from './Error.module.scss';

interface ErrorState {
  message?: string;
  statusCode?: number;
}

export function Error(): React.JSX.Element {
  const navigate = useNavigate();
  const location = useLocation();
  const { isDarkMode } = useTheme();
  const state = location.state as ErrorState | undefined;

  const errorMessage = state?.message ?? 'An unexpected error occurred';
  const statusCode = state?.statusCode ?? 500;

  const goHomeAction = {
    text: 'Go to Home',
    onClick: () => { void navigate(ROUTES.HOME); },
    renderIcon: Home,
    kind: 'tertiary' as const,
  };

  return (
    <PageLayout>
      <div className={styles.container}>
        {statusCode === 404 ? (
          <NotFoundEmptyState
            illustrationTheme={isDarkMode ? 'dark' : 'light'}
            title="Page not found"
            subtitle={errorMessage}
            action={goHomeAction}
          />
        ) : (
          <ErrorEmptyState
            illustrationTheme={isDarkMode ? 'dark' : 'light'}
            title="Something went wrong"
            subtitle={errorMessage}
            action={goHomeAction}
          />
        )}
      </div>
    </PageLayout>
  );
}
