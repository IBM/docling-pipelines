import React from 'react';
import { Content } from '@carbon/react';
import styles from './PageLayout.module.scss';

/**
 * Props for {@link PageLayout}.
 */
interface PageLayoutProps {
  /** Page content. */
  children: React.ReactNode;
  /**
   * When `true`, renders children directly inside Carbon's `Content` with no
   * inner padding or max-width container. Use for full-bleed two-zone pages
   * (e.g. Home, Projects, ProjectDetail).
   *
   * When `false` (default), wraps children in a centred `pageContainer` div
   * that applies standard side padding and a max content width.
   */
  fullBleed?: boolean;
}

/**
 * Top-level page wrapper that provides the main scroll region below the app header.
 *
 * Wraps Carbon's `Content` component and supports two layout modes:
 * - **Default**: centred, padded container suitable for standard content pages.
 * - **Full-bleed** (`fullBleed`): no container — children fill the full width and height,
 *   enabling custom two-zone layouts with independent scroll regions.
 */
export function PageLayout({ children, fullBleed = false }: PageLayoutProps): React.JSX.Element {
  return (
    <Content className={fullBleed ? styles.fullBleed : undefined}>
      {fullBleed ? children : (
        <div className={styles.pageContainer}>
          {children}
        </div>
      )}
    </Content>
  );
}
