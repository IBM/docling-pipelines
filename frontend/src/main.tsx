import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { Provider } from 'react-redux';
import '@carbon/styles/css/styles.css';
import '@carbon/ibm-products/css/index-without-carbon.css';
import '@carbon-labs/react-animated-header/scss/animated-header.scss';
import { ThemeProvider } from './contexts/ThemeProvider';
import { store } from './store';
import App from './App';

const rootElement = document.getElementById('root');

if (!rootElement) {
  throw new Error('Root element not found');
}

createRoot(rootElement).render(
  <StrictMode>
    <Provider store={store}>
      <ThemeProvider>
        <App />
      </ThemeProvider>
    </Provider>
  </StrictMode>
);
