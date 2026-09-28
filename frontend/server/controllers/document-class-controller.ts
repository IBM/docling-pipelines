import axios from 'axios';
import { log4js, logUtil } from '../../src/utils/logger';

const logger = log4js.getLogger('document-class.controller');

/**
 * Fetch document classes from backend API
 * BFF controller that proxies requests to the Python FastAPI backend
 */
const fetchDocumentClasses = async (req, res) => {
  try {
    const requestUrl = `${process.env.BACKEND_API_URL}/api/v1/document_classes`;
    logUtil.debug({ logger, message: 'Request URL', data: requestUrl });

    const response = await axios.get(requestUrl, {
      headers: {
        'Accept': 'application/json',
      },
    });

    res.json(response.data);

  } catch (error) {
    logUtil.error({ logger, message: 'Error fetching document classes', data: error.message });

    const status = error.response?.status ?? 500;
    const errorData = error.response?.data ?? { error: 'Failed to fetch document classes' };

    res.status(status).json(errorData);
  }
};

/**
 * Export routes function that registers all document class endpoints
 */
export const routes = (router) => {
  router.get('/documentClasses', fetchDocumentClasses);
};
