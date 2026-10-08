import { defineMessages } from 'react-intl';

export const messages = defineMessages({
  emptyTitle: {
    id: 'src.components.Canvas.FlowRunHistoryTearsheet.emptyTitle',
    defaultMessage: 'No runs yet',
  },
  emptySubtitle: {
    id: 'src.components.Canvas.FlowRunHistoryTearsheet.emptySubtitle',
    defaultMessage: 'Run this flow to see execution history here.',
  },
  downloadLogsDescription: {
    id: 'src.components.Canvas.FlowRunHistoryTearsheet.downloadLogsDescription',
    defaultMessage: 'Download logs',
  },
  statusCompleted: {
    id: 'src.components.Canvas.FlowRunHistoryTearsheet.statusCompleted',
    defaultMessage: 'Completed',
  },
  statusInProgress: {
    id: 'src.components.Canvas.FlowRunHistoryTearsheet.statusInProgress',
    defaultMessage: 'In progress',
  },
  statusRunWithIssues: {
    id: 'src.components.Canvas.FlowRunHistoryTearsheet.statusRunWithIssues',
    defaultMessage: 'Run with issues',
  },
  statusFailed: {
    id: 'src.components.Canvas.FlowRunHistoryTearsheet.statusFailed',
    defaultMessage: 'Failed',
  },
  statusCanceled: {
    id: 'src.components.Canvas.FlowRunHistoryTearsheet.statusCanceled',
    defaultMessage: 'Canceled',
  },
});
