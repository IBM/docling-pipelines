import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Home } from '@carbon/icons-react';
import { NotFoundEmptyState } from '@carbon/ibm-products';
import { PageLayout } from '@/components';
import { ROUTES } from '@/config';
import { useTheme } from '@/hooks';
import styles from './NotFound.module.scss';

export function NotFound(): React.JSX.Element {
  const navigate = useNavigate();
  const { isDarkMode } = useTheme();

  return (
    <PageLayout>
      <div className={styles.container}>
        <NotFoundEmptyState
          illustrationTheme={isDarkMode ? 'dark' : 'light'}
          title="Page not found"
          subtitle="The page you are looking for does not exist or has been moved."
          action={{
            text: 'Go to Home',
            onClick: () => { void navigate(ROUTES.HOME); },
            renderIcon: Home,
            kind: 'tertiary',
          }}
        />
      </div>
    </PageLayout>
  );
}
