import { defineMessages } from 'react-intl';

export const messages = defineMessages({
  title: {
    id: 'src.components.cards.FlowsCard.title',
    defaultMessage: 'Flows',
  },
  loading: {
    id: 'src.components.cards.FlowsCard.loading',
    defaultMessage: 'Loading flows...',
  },
  emptyTitle: {
    id: 'src.components.cards.FlowsCard.emptyTitle',
    defaultMessage: 'No recent flows',
  },
  emptySubtitle: {
    id: 'src.components.cards.FlowsCard.emptySubtitle',
    defaultMessage: 'Recent flows will be listed here.',
  },
  refreshDescription: {
    id: 'src.components.cards.FlowsCard.refreshDescription',
    defaultMessage: 'Refresh flows',
  },
  loadError: {
    id: 'src.components.cards.FlowsCard.loadError',
    defaultMessage: 'Failed to load flows.',
  },
});
