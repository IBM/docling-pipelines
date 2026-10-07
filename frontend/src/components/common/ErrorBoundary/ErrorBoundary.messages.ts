import { defineMessages } from 'react-intl';

export const messages = defineMessages({
  title: {
    id: 'src.components.common.ErrorBoundary.title',
    defaultMessage: 'Something went wrong',
  },
  tryAgain: {
    id: 'src.components.common.ErrorBoundary.tryAgain',
    defaultMessage: 'Try again',
  },
  errorDetails: {
    id: 'src.components.common.ErrorBoundary.errorDetails',
    defaultMessage: 'Error details (development only)',
  },
});
