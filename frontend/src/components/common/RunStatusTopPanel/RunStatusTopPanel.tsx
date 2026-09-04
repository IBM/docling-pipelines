/**
 * @fileoverview Top panel showing run statistics during pipeline execution.
 * Passed as topPanelContent to ElyraCanvas. Renders inside Elyra's .top-panel container.
 */

import React, { useMemo } from 'react';
import { Button } from '@carbon/react';
import { CheckmarkFilled, ErrorFilled, WarningAltFilled, Close, Maximize, Minimize } from '@carbon/icons-react';
import type { JobStats } from '@/types';
import { JOB_RUN_STATUS, COMPLETED_STATUSES } from '@/constants/jobRunStatus';
import { WARNING_NODE_STATUSES } from '@/constants/canvasActions';
import { formatElapsedTime } from '@/utils/dateTimeUtils';
import styles from './RunStatusTopPanel.module.scss';

interface RunStatusTopPanelProps {
  jobStats: JobStats;
  isMinimized: boolean;
  isRunning: boolean;
  isStopDisabled: boolean;
  onToggleMinimize: () => void;
  onClose: () => void;
  onStop: () => void;
  onRunAgain: () => void;
}

/**
 * Compute node status counts from job_stats.node_stats.
 */
function computeNodeCounts(jobStats: JobStats) {
  const nodeStatsList = Object.values(jobStats.node_stats);
  const completed = nodeStatsList.filter((n) => n.node_status.toLowerCase() === JOB_RUN_STATUS.COMPLETED.toLowerCase()).length;
  const failed = nodeStatsList.filter((n) => n.node_status.toLowerCase() === JOB_RUN_STATUS.FAILED.toLowerCase()).length;
  const warning = nodeStatsList.filter((n) =>
    WARNING_NODE_STATUSES.has(n.node_status.toLowerCase())
  ).length;
  // When there are no node-level stats but the run is in a terminal state,
  // show the bar at 100% so the status colour is visible.
  const isTerminal = COMPLETED_STATUSES.has(jobStats.status);
  const progress = nodeStatsList.length
    ? ((completed + failed + warning) / nodeStatsList.length) * 100
    : isTerminal ? 100 : 0;

  return { completed, failed, warning, progress, total: nodeStatsList.length };
}

/**
 * Derive progress bar fill class based on current status.
 * Accepts pre-computed nodeCounts to avoid calling computeNodeCounts twice per render.
 */
/**
 * Derive progress bar fill class from the top-level run status.
 * Mirrors datasift-ui getProgressClassName(progressStatus) exactly —
 * the bar colour is driven by the job's overall status, never by node counts.
 */
function getProgressFillClass(status: string): string {
  switch (status) {
    case JOB_RUN_STATUS.COMPLETED:
      return styles.progressCompleted ?? '';
    case JOB_RUN_STATUS.FAILED:
      return styles.progressFailed ?? '';
    case JOB_RUN_STATUS.WARNING:
    case JOB_RUN_STATUS.COMPLETED_WITH_ERRORS:
    case JOB_RUN_STATUS.COMPLETED_WITH_WARNINGS:
      return styles.progressWarning ?? '';
    case JOB_RUN_STATUS.CANCELED:
    case JOB_RUN_STATUS.CANCELING:
      return styles.progressCanceled ?? '';
    default:
      // Running, Starting, Pending, Queued, Resuming, Paused → blue
      return styles.progressRunning ?? '';
  }
}

export function RunStatusTopPanel({
  jobStats,
  isMinimized,
  isRunning,
  isStopDisabled,
  onToggleMinimize,
  onClose,
  onStop,
  onRunAgain,
}: RunStatusTopPanelProps): React.JSX.Element {
  const nodeCounts = useMemo(() => computeNodeCounts(jobStats), [jobStats]);
  const elapsedTimeStr = useMemo(() => formatElapsedTime(jobStats.duration), [jobStats.duration]);
  const progressFillClass = useMemo(() => getProgressFillClass(jobStats.status), [jobStats.status]);

  return (
    <div className={styles.topPanelContent}>
      {!isMinimized && (
        <>
          {/* Section columns + Minimize/Close — direct children of topRow, no extra wrapper */}
          <div className={styles.topRow}>
            <div className={styles.sectionColumns}>
              {/* Orchestrator */}
              <div className={styles.sectionGroup}>
                <p className={styles.sectionHeader}>Orchestrator</p>
                <p>{jobStats.orchestrator}</p>
              </div>

              <div className={styles.runDetailsDividerLine} />

              {/* Duration */}
              <div className={styles.sectionGroup}>
                <p className={styles.sectionHeader}>Duration</p>
                <p>{elapsedTimeStr}</p>
              </div>

              <div className={styles.runDetailsDividerLine} />

              {/* Nodes */}
              <div className={styles.sectionGroup}>
                <p className={styles.sectionHeader}>Nodes</p>
                <div className={styles.statusGroupRow}>
                  <div className={styles.statusItem}>
                    <div className={styles.statusLabelRow}>
                      <CheckmarkFilled size={16} className={styles.checkmarkFilled} />
                      <span>Completed</span>
                    </div>
                    <p>{nodeCounts.completed}</p>
                  </div>
                  <div className={styles.statusItem}>
                    <div className={styles.statusLabelRow}>
                      <ErrorFilled size={16} className={styles.errorFilled} />
                      <span>Failed</span>
                    </div>
                    <p>{nodeCounts.failed}</p>
                  </div>
                  <div className={styles.statusItem}>
                    <div className={styles.statusLabelRow}>
                      <WarningAltFilled size={16} className={styles.warningAltFilled} />
                      <span>Warning</span>
                    </div>
                    <p>{nodeCounts.warning}</p>
                  </div>
                </div>
              </div>

              <div className={styles.runDetailsDividerLine} />

              {/* Documents */}
              <div className={styles.sectionGroup}>
                <p className={styles.sectionHeader}>Documents</p>
                <div className={styles.statusGroupRow}>
                  <div className={styles.statusItem}>
                    <p>In scope</p>
                    <p>{jobStats.total_docs}</p>
                  </div>
                  <div className={styles.statusItem}>
                    <p>Processed</p>
                    <p>{jobStats.completed_docs ?? 0}</p>
                  </div>
                  <div className={styles.statusItem}>
                    <p>Skipped</p>
                    <p>{jobStats.skipped_docs}</p>
                  </div>
                  <div className={styles.statusItem}>
                    <p>Failed</p>
                    <p>{jobStats.failed_docs}</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Minimize + Close — sibling of sectionColumns, right-aligned inside topRow */}
            <div className={styles.topPanelRightIcons}>
              <button className={styles.topPanelIconButton} onClick={onToggleMinimize} title="Minimize">
                <Minimize size={20} />
              </button>
              <button className={styles.topPanelIconButton} onClick={onClose} title="Close">
                <Close size={20} />
              </button>
            </div>
          </div>

          {/* Progress — hr separator THEN status text THEN bar + button */}
          <div className={styles.progressDiv}>
            <hr className={styles.borderSolid} />
            <p className={styles.progressStatus}>{jobStats.status}</p>
            <div className={styles.progressSection}>
              <div className={styles.progressBar}>
                <div className={progressFillClass} style={{ width: `${nodeCounts.progress}%` }} />
              </div>
              <div className={styles.progressAction}>
                {/* Single button — mirrors datasift-ui: isRunning drives label+handler,
                    isStopDisabled only controls the disabled attribute.
                    "Run Again" only appears once isRunning=false, which happens after
                    the final 5-second confirmation poll completes. */}
                <Button
                  kind="secondary"
                  size="sm"
                  disabled={isRunning ? isStopDisabled : false}
                  onClick={isRunning ? onStop : onRunAgain}
                >
                  {isRunning ? 'Stop' : 'Run Again'}
                </Button>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Minimized state — status text + maximize/close */}
      {isMinimized && (
        <div className={styles.runDetailsTopRowDiv}>
          <p className={styles.progressStatusMinimize}>{jobStats.status}</p>
          <div className={styles.topPanelRightIcons}>
            <button className={styles.topPanelIconButton} onClick={onToggleMinimize} title="Maximize">
              <Maximize size={20} />
            </button>
            <button className={styles.topPanelIconButton} onClick={onClose} title="Close">
              <Close size={20} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
