import React, { useCallback, useEffect, useState } from 'react';
import { Button } from '@carbon/react';
import { Download } from '@carbon/icons-react';
import { NoDataEmptyState } from '@carbon/ibm-products';
import { useNavigate } from 'react-router-dom';
import { SharedDataTable, SharedTearsheet } from '@/components/common';
import {
  FLOW_RUN_HISTORY_HEADERS,
  FLOW_RUN_HISTORY_TITLE,
  DOWNLOAD_ENABLED_STATUSES,
} from '@/constants/flowRunHistory';
import { API_STATUS_MAP } from '@/constants/flowStatus';
import { getJobRuns } from '@/services/api';
import { getJobRun } from '@/services/api/actions/job-run-actions';
import { generateRoute } from '@/config';
import type { JobRunListItem } from '@/types';
import { StatusIcon, STATUS_LABELS } from '@/components/FlowDetail';
import type { RunStatus } from '@/components/FlowDetail';
import { getJobRunStatusLabel } from '@/constants/jobRunStatus';
import { formatEpochToDisplay, formatElapsedTime } from '@/utils/dateTimeUtils';
import { useTheme } from '@/hooks';
import styles from './FlowRunHistoryTearsheet.module.scss';

export interface FlowRunHistoryTearsheetProps {
  open: boolean;
  onClose: () => void;
  /** Flow ID used to fetch job runs. When undefined, the table stays empty. */
  flowId?: string;
  /** project_id query param carried through to the run details URL. */
  projectId?: string;
}

/** Long-form locale options for tearsheet timestamp display (e.g. "August 5, 2024 at 6:26 AM"). */
const TIMESTAMP_OPTIONS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
  hour12: true,
};

/**
 * Downloads execution logs for a job run as a `.txt` file.
 * Mirrors docling-pipelines-ui handleDownloadLogs: fetches with include_logs=true,
 * concatenates per-node log strings from node_sequence, saves as text.
 */
function triggerDownloadLogs(runId: string, timestamp: string): void {
  void getJobRun(runId, true).then((res) => {
    const data = res.data as { node_sequence?: string[]; error_logs?: string } & Record<string, unknown>;
    let logs = '';

    if (data.node_sequence?.length) {
      data.node_sequence.forEach((nodeId) => {
        const nodeLog = data[nodeId];
        if (typeof nodeLog === 'string') { logs += nodeLog; }
      });
    } else {
      logs = JSON.stringify(data, null, 2);
    }

    if (data.error_logs && typeof data.error_logs === 'string') {
      logs += `\nError stack trace:\n${data.error_logs}`;
    }

    const blob = new Blob([logs], { type: 'text/plain' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${timestamp}_log.txt`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
  });
}

export function FlowRunHistoryTearsheet({
  open,
  onClose,
  flowId,
  projectId = '',
}: FlowRunHistoryTearsheetProps): React.JSX.Element {
  const navigate = useNavigate();
  const { isDarkMode } = useTheme();
  const [rawItems, setRawItems] = useState<JobRunListItem[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchRuns = useCallback((): void => {
    if (!flowId) { return; }
    setLoading(true);
    getJobRuns({ job_id: flowId })
      .then((res) => {
        setRawItems(res.data.list);
      })
      .catch(() => {
        // Non-fatal: keep existing rows on error.
      })
      .finally(() => {
        setLoading(false);
      });
  }, [flowId]);

  // Fetch whenever the tearsheet opens or the flowId changes.
  useEffect(() => {
    if (open && flowId) {
      fetchRuns();
    }
  }, [open, flowId, fetchRuns]);

  // Build rows — timestamp is a clickable link navigating to the run details page.
  const rows = rawItems.map((item) => {
    const timestamp = formatEpochToDisplay(item.start_time, TIMESTAMP_OPTIONS) || '—';
    const canDownload = DOWNLOAD_ENABLED_STATUSES.has(item.status);
    const uiStatus = (API_STATUS_MAP[item.status] ?? null) as RunStatus | null;
    return {
      id: item.job_run_id,
      timestamp: (
        <button
          type="button"
          className={styles.timestampLink}
          onClick={() => {
            if (flowId) {
              onClose();
              void navigate(generateRoute.runDetails(flowId, item.job_run_id, projectId));
            }
          }}
        >
          {timestamp}
        </button>
      ),
      status: uiStatus ? (
        <span className={styles.statusCell}>
          <StatusIcon status={uiStatus} iconStyles={styles} />
          {STATUS_LABELS[uiStatus]}
        </span>
      ) : getJobRunStatusLabel(item.status),
      duration: formatElapsedTime(item.duration),
      logs: canDownload ? (
        <Button
          kind="ghost"
          size="sm"
          renderIcon={Download}
          iconDescription="Download logs"
          hasIconOnly
          onClick={() => { triggerDownloadLogs(item.job_run_id, timestamp); }}
        />
      ) : null,
    };
  });

  const emptyState = (
    <NoDataEmptyState
      illustrationTheme={isDarkMode ? 'dark' : 'light'}
      illustrationPosition="top"
      size="sm"
      title="No runs yet"
      subtitle="Run this flow to see execution history here."
    />
  );

  return (
    <SharedTearsheet
      open={open}
      onClose={onClose}
      title={FLOW_RUN_HISTORY_TITLE}
      hideFooter
    >
      <div className={styles.tearsheetContent}>
        <SharedDataTable
          headers={FLOW_RUN_HISTORY_HEADERS}
          rows={rows}
          loading={loading}
          emptyState={emptyState}
        />
      </div>
    </SharedTearsheet>
  );
}
