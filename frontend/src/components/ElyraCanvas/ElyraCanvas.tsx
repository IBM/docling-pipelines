import React, { useRef, useEffect, useMemo } from 'react';
import { CommonCanvas, CanvasController } from '@elyra/canvas';
import type {
  PipelineFlowDef,
  CanvasConfig as ElyraCanvasConfig,
  ToolbarConfig as ElyraToolbarConfig,
} from '@elyra/canvas';
import { CardNodeWrapper } from './CardNodeWrapper';
import { log4js, logUtil } from '@/utils/logger';
import type { PaletteData } from '@/types/palette';
import type { ContextMenuHandler, EditActionHandler, ClickActionHandler } from '@/types/canvas';
import '@elyra/canvas/dist/styles/common-canvas.min.css';
import '@carbon/charts-react/styles.min.css';
import styles from './ElyraCanvas.module.scss';

const logger = log4js.getLogger('ElyraCanvas');

interface ElyraCanvasProps {
  pipelineFlow?: PipelineFlowDef;
  palette?: PaletteData;
  canvasConfig: ElyraCanvasConfig;
  toolbarConfig?: ElyraToolbarConfig;
  contextMenuHandler?: ContextMenuHandler;
  editActionHandler?: EditActionHandler;
  clickActionHandler?: ClickActionHandler;
  /**
   * Called when a hotspot decoration on a link or node is clicked.
   * Elyra signature: (object, decorationId, pipelineId)
   * where `object` is the canvas node/link the decoration belongs to.
   */
  decorationActionHandler?: (object: unknown, id: string, pipelineId: string) => void;
  onCanvasControllerReady?: (controller: CanvasController) => void;
  rightFlyoutContent?: React.ReactNode;
  showRightFlyout?: boolean;
  /** Content rendered in the resizable bottom panel (e.g. validation notification table). */
  bottomPanelContent?: React.ReactNode;
  /** Whether the bottom panel is visible. */
  showBottomPanel?: boolean;
  /** Content rendered above the canvas toolbar (e.g. top notification alert bar). */
  topPanelContent?: React.ReactNode;
  /** Whether the top panel is visible. */
  showTopPanel?: boolean;
}

/**
 * Carbon Charts node layout configuration.
 * This is component-specific and will be merged with parent canvasConfig.
 */
const CARD_NODE_LAYOUT_CONFIG = {
  nodeExternalObject: CardNodeWrapper,
  defaultNodeWidth: 208,
  defaultNodeHeight: 68,
  nodeShapeDisplay: false,
  imageDisplay: false,
  labelDisplay: false,

  // Port configuration
  inputPortObject: 'image',
  inputPortImage: '/ui/images/decorations/dragStateArrow.svg',
  inputPortWidth: 20,
  inputPortHeight: 20,

  outputPortObject: 'image',
  outputPortImage: '/ui/images/decorations/dragStateArrow.svg',
  outputPortWidth: 20,
  outputPortHeight: 20,
  outputPortRightPosX: 5,
  outputPortRightPosY: 30,

  // Link drawing from node center for smoother curves
  drawNodeLinkLineFromTo: 'node_center',
  drawCommentLinkLineTo: 'node_center',

  // Context toolbar and ellipsis
  contextToolbarPosition: 'topRight',
  ellipsisPosition: 'topRight',
  ellipsisWidth: 30,
  ellipsisHeight: 30,
  ellipsisPosY: -35,
  ellipsisPosX: -30,
} as const;

/**
 * Wrapper for Elyra's CommonCanvas with Carbon Charts node styling.
 * Merges parent canvasConfig with card-specific node layout configuration.
 * Wrap in ErrorBoundary for production use.
 */
export function ElyraCanvas({
  pipelineFlow,
  palette,
  canvasConfig,
  toolbarConfig,
  contextMenuHandler,
  editActionHandler,
  clickActionHandler,
  decorationActionHandler,
  onCanvasControllerReady,
  rightFlyoutContent,
  showRightFlyout = false,
  bottomPanelContent,
  showBottomPanel = false,
  topPanelContent,
  showTopPanel = false,
}: ElyraCanvasProps): React.JSX.Element {
  const canvasController = useMemo(() => new CanvasController(), []);
  const canvasRef = useRef<HTMLDivElement>(null);
  // Load the pipeline flow only once — on the first non-null value.
  // Subsequent prop changes must NOT call setPipelineFlow again: that resets
  // node positions to the backend values (which may differ after a save).
  const initialFlowLoadedRef = useRef(false);

  // Notify parent when canvas controller is ready
  useEffect(() => {
    if (onCanvasControllerReady) {
      onCanvasControllerReady(canvasController);
    }
  }, [canvasController, onCanvasControllerReady]);

  // Fit the canvas to the viewport once on mount.
  // requestAnimationFrame defers until after Elyra's componentDidMount + D3 layout
  // have completed and the SVG has real dimensions to fit against.
  // Empty deps — intentional: runs once per mount, never on re-renders, so
  // subsequent pipelineFlow changes (e.g. after save) never reset the user's zoom.
  useEffect(() => {
    const rafId = requestAnimationFrame(() => { canvasController.zoomToFit(); });
    return () => { cancelAnimationFrame(rafId); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Merge parent config with card node layout config
  const mergedConfig = useMemo(
    () => ({
      ...canvasConfig,
      enableNodeLayout: {
        ...canvasConfig.enableNodeLayout,
        ...CARD_NODE_LAYOUT_CONFIG,
      },
    }),
    [canvasConfig]
  );

  useEffect(() => {
    if (palette) {
      canvasController.setPipelineFlowPalette(palette);
      logUtil.info({
        logger,
        message: 'Palette loaded with categories',
        data: { categories: palette.categories.length },
      });
    }
  }, [palette, canvasController]);

  // Guard: do not render CommonCanvas until the flow is loaded.
  // setPipelineFlow is called synchronously here (during render, before CommonCanvas
  // mounts) so Elyra never reads nodes from an empty controller.
  if (!pipelineFlow) {
    return <div className={styles.canvasContainer} />;
  }

  if (!initialFlowLoadedRef.current) {
    canvasController.setPipelineFlow(pipelineFlow);
    initialFlowLoadedRef.current = true;
  }

  return (
    <div className={styles.canvasContainer} ref={canvasRef}>
      <CommonCanvas
        canvasController={canvasController}
        config={mergedConfig}
        toolbarConfig={toolbarConfig}
        contextMenuHandler={contextMenuHandler}
        editActionHandler={editActionHandler}
        clickActionHandler={clickActionHandler}
        decorationActionHandler={decorationActionHandler}
        rightFlyoutContent={rightFlyoutContent}
        showRightFlyout={showRightFlyout}
        bottomPanelContent={bottomPanelContent}
        showBottomPanel={showBottomPanel}
        topPanelContent={topPanelContent}
        showTopPanel={showTopPanel}
      />
    </div>
  );
}
