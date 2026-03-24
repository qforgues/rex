/**
 * FreshBooks API Service
 * Handles communication with the FreshBooks API, including authentication
 * and fetching invoice data.
 */

const https = require('https');
require('dotenv').config();

// FreshBooks API base URL
const FRESHBOOKS_API_BASE = 'https://api.freshbooks.com';

/**
 * Retrieves the FreshBooks account ID from environment variables.
 * @returns {string} The account ID.
 * @throws {Error} If the account ID is not configured.
 */
function getAccountId() {
  const accountId = process.env.FRESHBOOKS_ACCOUNT_ID;
  if (!accountId) {
    throw new Error('FRESHBOOKS_ACCOUNT_ID is not configured in environment variables.');
  }
  return accountId;
}

/**
 * Retrieves the FreshBooks access token from environment variables.
 * @returns {string} The access token.
 * @throws {Error} If the access token is not configured.
 */
function getAccessToken() {
  const token = process.env.FRESHBOOKS_ACCESS_TOKEN;
  if (!token) {
    throw new Error('FRESHBOOKS_ACCESS_TOKEN is not configured in environment variables.');
  }
  return token;
}

/**
 * Makes an authenticated HTTP GET request to the FreshBooks API.
 * @param {string} path - The API path to request.
 * @returns {Promise<object>} The parsed JSON response.
 */
function makeApiRequest(path) {
  return new Promise((resolve, reject) => {
    const accessToken = getAccessToken();
    const url = `${FRESHBOOKS_API_BASE}${path}`;

    const options = {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'Api-Version': 'alpha',
      },
    };

    const req = https.request(url, options, (res) => {
      let data = '';

      res.on('data', (chunk) => {
        data += chunk;
      });

      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);

          // Handle HTTP-level errors from FreshBooks
          if (res.statusCode === 401) {
            return reject(new Error('FreshBooks authentication failed. Check your access token.'));
          }

          if (res.statusCode === 403) {
            return reject(new Error('FreshBooks authorization error. Insufficient permissions.'));
          }

          if (res.statusCode === 404) {
            return reject(new Error(`FreshBooks resource not found: ${path}`));
          }

          if (res.statusCode === 429) {
            return reject(new Error('FreshBooks API rate limit exceeded. Please try again later.'));
          }

          if (res.statusCode >= 500) {
            return reject(new Error(`FreshBooks server error (${res.statusCode}). Please try again later.`));
          }

          if (res.statusCode < 200 || res.statusCode >= 300) {
            return reject(new Error(`Unexpected FreshBooks API response: HTTP ${res.statusCode}`));
          }

          resolve(parsed);
        } catch (parseError) {
          reject(new Error(`Failed to parse FreshBooks API response: ${parseError.message}`));
        }
      });
    });

    req.on('error', (networkError) => {
      reject(new Error(`Network error communicating with FreshBooks: ${networkError.message}`));
    });

    // Set a timeout to avoid hanging requests
    req.setTimeout(10000, () => {
      req.destroy();
      reject(new Error('FreshBooks API request timed out after 10 seconds.'));
    });

    req.end();
  });
}

/**
 * Normalizes a raw FreshBooks invoice object into a consistent format
 * suitable for the application UI.
 * @param {object} invoice - Raw invoice object from FreshBooks API.
 * @returns {object} Normalized invoice object.
 */
function normalizeInvoice(invoice) {
  return {
    id: invoice.id || invoice.invoiceid,
    invoiceNumber: invoice.invoice_number || invoice.number || '',
    status: invoice.v3_status || invoice.status || 'unknown',
    clientId: invoice.customerid || invoice.client_id || null,
    clientName: invoice.current_organization || invoice.client_name || 'Unknown Client',
    amount: {
      total: invoice.amount ? invoice.amount.amount : '0.00',
      currency: invoice.amount ? invoice.amount.code : 'USD',
    },
    amountOutstanding: {
      total: invoice.outstanding ? invoice.outstanding.amount : '0.00',
      currency: invoice.outstanding ? invoice.outstanding.code : 'USD',
    },
    createdAt: invoice.create_date || invoice.created_at || null,
    dueDate: invoice.due_date || null,
    description: invoice.description || '',
    lines: Array.isArray(invoice.lines) ? invoice.lines.map((line) => ({
      id: line.lineid,
      description: line.description || '',
      quantity: line.qty || 0,
      unitCost: line.unit_cost ? line.unit_cost.amount : '0.00',
      amount: line.amount ? line.amount.amount : '0.00',
    })) : [],
  };
}

/**
 * Fetches invoice data from the FreshBooks API.
 * Retrieves all invoices for the configured account, normalized for UI consumption.
 *
 * @returns {Promise<object>} An object containing the list of invoices and metadata.
 * @throws {Error} On network errors, authentication failures, or unexpected API responses.
 *
 * @example
 * const { invoices, total } = await fetchInvoices();
 */
async function fetchInvoices() {
  const accountId = getAccountId();
  const path = `/accounting/account/${accountId}/invoices/invoices`;

  const response = await makeApiRequest(path);

  // Validate the expected response structure
  if (!response || !response.response) {
    throw new Error('Unexpected FreshBooks API response structure: missing response object.');
  }

  const result = response.response.result;

  if (!result || !result.invoices) {
    // Return empty list if no invoices found rather than throwing
    return {
      invoices: [],
      total: 0,
      pages: 0,
      perPage: 0,
      page: 1,
    };
  }

  const normalizedInvoices = result.invoices.map(normalizeInvoice);

  return {
    invoices: normalizedInvoices,
    total: result.total || normalizedInvoices.length,
    pages: result.pages || 1,
    perPage: result.per_page || normalizedInvoices.length,
    page: result.page || 1,
  };
}

module.exports = {
  fetchInvoices,
  // Export internals for unit testing
  normalizeInvoice,
  makeApiRequest,
};
