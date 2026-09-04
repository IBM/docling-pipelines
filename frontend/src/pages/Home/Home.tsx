import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Grid, Column, Button } from '@carbon/react';
import { go } from '@/utils';
import { RecentlyViewed } from '@carbon/icons-react';
import {
  AnimatedHeader,
  watsonXAnimatedLight,
  watsonXStaticLight,
  watsonXAnimatedDark,
  watsonXStaticDark,
  type Tile,
  type TileGroup,
  type AriaLabels,
} from '@carbon-labs/react-animated-header';
import { ROUTES, generateRoute } from '@/config';
import { useTheme } from '@/hooks';
import { useAppSelector } from '@/hooks/useAppSelector';
import { useRecentlyVisited } from '@/hooks/useRecentlyVisited';
import { selectProjectsArray } from '@/selectors/projectsSelectors';
import { selectFlowsArray } from '@/selectors/flowSelectors';
import { PageLayout, ProjectsCard, RunsCard, FlowsCard } from '@/components';
import { TileContent } from '@/components/TileContent';
import { SampleProjectModal } from '@/components/common/SampleProjectModal';
import styles from './Home.module.scss';

const ARIA_LABELS: AriaLabels = {
  welcome: 'Welcomes the user',
  description: 'Short description of the product',
  collapseButton: 'Collapse header details',
  expandButton: 'Expand header details',
  tilesContainer: 'Feature tiles list',
};

const MAX_RECENT = 4;

export function Home(): React.JSX.Element {
  const navigate = useNavigate();
  const { theme } = useTheme();
  const [sampleModalOpen, setSampleModalOpen] = useState(false);

  // localStorage LRU list — populated as the user opens projects / flows
  const { recent } = useRecentlyVisited();
  // API data from the card fetches — used as fallback when localStorage is empty
  const projects = useAppSelector(selectProjectsArray);
  const flows = useAppSelector(selectFlowsArray);

  // Primary: user-opened order from localStorage (most recently opened first).
  // Fallback: when localStorage is empty (first visit / cleared), derive chips
  // from the API data already fetched by ProjectsCard and FlowsCard, sorted by
  // modifiedOn descending so the newest items appear first.
  const recentChips = useMemo(() => {
    if (recent.length > 0) {
      return recent.slice(0, MAX_RECENT);
    }

    type Sortable = { id: string; label: string; path: string; type: 'project' | 'flow'; sortKey: string };

    const projectItems: Sortable[] = projects.map((p) => ({
      id: `project-${p.id}`,
      label: p.name,
      path: generateRoute.projectDetail(p.id),
      type: 'project' as const,
      sortKey: p.modifiedOn,
    }));

    const flowItems: Sortable[] = flows.map((f) => ({
      id: `flow-${f.flow_id}`,
      label: f.name,
      path: f.project_id
        ? generateRoute.flowDetail(f.flow_id, f.project_id)
        : ROUTES.PROJECTS,
      type: 'flow' as const,
      sortKey: f.modified_on,
    }));

    return [...projectItems, ...flowItems]
      .sort((a, b) => {
        const ta = new Date(a.sortKey).getTime();
        const tb = new Date(b.sortKey).getTime();
        return (Number.isNaN(tb) ? 0 : tb) - (Number.isNaN(ta) ? 0 : ta);
      })
      .slice(0, MAX_RECENT)
      .map(({ id, label, path, type }) => ({ id, label, path, type }));
  }, [recent, projects, flows]);

  // Build tile groups — navigate is no longer used inside this memo
  // (the sample tile opens a modal; the learn tile uses href directly).
  const headerTiles: TileGroup[] = useMemo(() => [
    {
      id: 1,
      label: 'Quick start',
      tiles: [
        {
          tileId: 'tile-sample',
          variant: 'glass' as const,
          ariaLabel: 'Get started with sample project',
          customContent: (
            <TileContent
              label="Sample project"
              title="Get started with sample data"
              subtitle="Guided journeys for pipeline creation"
              buttonLabel="Start"
              onAction={() => { setSampleModalOpen(true); }}
            />
          ),
        },
        {
          tileId: 'tile-learn',
          variant: 'glass' as const,
          ariaLabel: 'Learn more about the product',
          customContent: (
            <TileContent
              label="Learn more"
              title="See how it works"
              subtitle="View demos and documents"
              buttonLabel="Learn more"
              href="https://pages.github.ibm.com/wdp-gov/docling-pipelines/book/site/docling-pipelines/1.0/index.html"
            />
          ),
        },
      ],
    },
  ], []);

  const defaultTileGroup: TileGroup | undefined = headerTiles[0];
  const [selectedTileGroup, setSelectedTileGroup] = useState<TileGroup | undefined>(defaultTileGroup);

  // TODO: wire tileClickHandler for API integration (e.g. analytics or deep-link on tile click)
  // Navigation is currently driven by the Button inside customContent — tile-level click is unused
  const handleTileClick = (_tile: Tile): void => {};

  return (
    <PageLayout fullBleed>

      <SampleProjectModal
        open={sampleModalOpen}
        onClose={() => { setSampleModalOpen(false); }}
        onSuccess={(url) => { setSampleModalOpen(false); void navigate(url); }}
      />

      {/* Zone 1: Welcome Banner — AnimatedHeader */}
      {/* data-carbon-theme scopes AnimatedHeader's own token overrides;
          app 'white' → header g10 (same light family),
          app 'g100'  → header g100 (dark) */}
      <div
        className={styles.animatedHeaderWrapper}
        data-carbon-theme={theme === 'g100' ? 'g100' : 'g10'}
      >
        <AnimatedHeader
          welcomeText="Welcome"
          description="Build unstructured data pipelines and unlock your data's full potential."
          productName="Docling Pipelines"
          ariaLabels={ARIA_LABELS}
          headerAnimation={(theme === 'g100' ? watsonXAnimatedDark : watsonXAnimatedLight) as object}
          headerStatic={(theme === 'g100' ? watsonXStaticDark : watsonXStaticLight) as string}
          allTileGroups={headerTiles}
          selectedTileGroup={selectedTileGroup}
          setSelectedTileGroup={setSelectedTileGroup}
          tileClickHandler={handleTileClick}
        />
      </div>

      {/* Zone 2: Recently Visited — hidden when cache is empty */}
      {recentChips.length > 0 && (
        <div className={styles.recentBar}>
          <Grid>
            <Column sm={4} md={8} lg={16}>
              <div className={styles.recentBarInner}>
                <div className={styles.recentBarLabel}>
                  <span className={styles.recentBarHeading}>Overview</span>
                  <span className={styles.recentBarSub}>
                    <RecentlyViewed size={16} aria-hidden="true" />
                    Recently visited
                  </span>
                </div>
                <div className={styles.recentItems}>
                  {recentChips.map((item) => (
                    <Button
                      key={item.id}
                      kind="ghost"
                      size="sm"
                      onClick={() => { go(navigate, item.path); }}
                      className={styles.recentItem}
                    >
                      <span className={styles.recentItemType}>
                        {item.type.charAt(0).toUpperCase() + item.type.slice(1)} /
                      </span>
                      <span className={styles.recentItemName}>{item.label}</span>
                    </Button>
                  ))}
                </div>
              </div>
            </Column>
          </Grid>
        </div>
      )}

      {/* Zone 3: Recent Work + Card Grid */}
      <div className={styles.cardZone}>
        <Grid>
          <Column sm={4} md={8} lg={16}>
            <div className={styles.cardZoneInner}>
              <h2 className={styles.cardZoneHeading}>Recent work</h2>
              <div className={styles.cardGrid}>
                <ProjectsCard />
                <FlowsCard />
                <RunsCard />
              </div>
            </div>
          </Column>
        </Grid>
      </div>

    </PageLayout>
  );
}
