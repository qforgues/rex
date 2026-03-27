/**
 * Unit Tests: FreshBooks API Service
 * Tests the fetchInvoices() function and supporting utilities
 * using mocked HTTP responses to simulate FreshBooks API behavior.
 */

// Mock the https module before requiring the service
jest.mock('https');

const https = require('https');
const { fetchInvoices, normalizeInvoice } = require('../../server/services/freshBooksApi');

// ─── Helpers ────────────────────────────────────────────────────────────────

/**
 * Creates a mock https.request that simulates a FreshBooks API response.
 * @param {number} statusCode - HTTP status code to simulate.
 * @param {object|string} body - Response body (object will be JSON-stringified).
 * @param {Error|null} requestError - Optional error to emit on the request.
 * @param {boolean} timeout - Whether to simulate a timeout.
 */
function mockHttpsRequest(statusCode, body, requestError = null, timeout = false) {
  const responseData = typeof body === 'string' ? body : JSON.stringify(body);

  const mockResponse = {
    statusCode,
    on: jest.fn((event, handler) => {
      if (event === 'data') handler(responseData);
      if (event === 'end') handler();
    }),
  };

  const mockRequest = {
    on: jest.fn((event, handler) => {
      if (event === 'error' && requestError) handler(requestError);
    }),
    setTimeout: jest.fn((ms, handler) => {
      if (timeout) handler();
    }),
    destroy: jest.fn(),
    end: jest.fn(),
  };

  https.request.mockImplementation((url, options, callback) => {
    if (!requestError && !timeout) {
      callback(mockResponse);
    }
    return mockRequest;
  });

  return { mockRequest, mockResponse };
}

// ─── Environment Setup ───────────────────────────────────────────────────────

beforeEach(() => {
  jest.clearAllMocks();
  process.env.FRESHBOOKS_ACCESS_TOKEN = 'test-access-token';
  process.env.FRESHBOOKS_ACCOUNT_ID = 'test-account-id';
});

afterEach(() => {
  delete process.env.FRESHBOOKS_ACCESS_TOKEN;
  delete process.env.FRESHBOOKS_ACCOUNT_ID;
});

// ─── fetchInvoices() Tests ───────────────────────────────────────────────────

describe('fetchInvoices()', () => {
  const mockApiResponse = {
    response: {
      result: {
        invoices: [
          {
            id: 1001,
            invoice_number: 'INV-001',
            v3_status: 'paid',
            customerid: 42,
            current_organization: 'Acme Corp',
            amount: { amount: '1500.00', code: 'USD' },
            outstanding: { amount: '0.00', code: 'USD' },
            create_date: '2024-01-15',
            due_date: '2024-02-15',
            description: 'Web development services',
            lines: [
              {
                lineid: 1,
                description: 'Frontend development',
                qty: 10,
                unit_cost: { amount: '150.00' },
                amount: { amount: '1500.00' },
              },
            ],
          },
          {
            id: 1002,
            invoice_number: 'INV-002',
            v3_status: 'sent',
            customerid: 43,
            current_organization: 'Beta LLC',
            amount: { amount: '800.00', code: 'USD' },
            outstanding: { amount: '800.00', code: 'USD' },
            create_date: '2024-02-01',
            due_date: '2024-03-01',
            description: 'Consulting',
            lines: [],
          },
        ],
        total: 2,
        pages: 1,
        per_page: 15,
        page: 1,
      },
    },
  };

  test('returns normalized invoice data on success', async () => {
    mockHttpsRequest(200, mockApiResponse);

    const result = await fetchInvoices();

    expect(result).toHaveProperty('invoices');
    expect(result.invoices).toHaveLength(2);
    expect(result.total).toBe(2);
    expect(result.pages).toBe(1);

    const first = result.invoices[0];
    expect(first.id).toBe(1001);
    expect(first.invoiceNumber).toBe('INV-001');
    expect(first.status).toBe('paid');
    expect(first.clientName).toBe('Acme Corp');
    expect(first.amount.total).toBe('1500.00');
    expect(first.amount.currency).toBe('USD');
    expect(first.lines).toHaveLength(1);
    expect(first.lines[0].description).toBe('Frontend development');
  });

  test('returns empty invoices array when result has no invoices', async () => {
    mockHttpsRequest(200, {
      response: {
        result: {},
      },
    });

    const result = await fetchInvoices();

    expect(result.invoices).toEqual([]);
    expect(result.total).toBe(0);
  });

  test('throws authentication error on 401 response', async () => {
    mockHttpsRequest(401, { error: 'Unauthorized' });

    await expect(fetchInvoices()).rejects.toThrow('authentication failed');
  });

  test('throws authorization error on 403 response', async () => {
    mockHttpsRequest(403, { error: 'Forbidden' });

    await expect(fetchInvoices()).rejects.toThrow('authorization error');
  });

  test('throws not found error on 404 response', async () => {
    mockHttpsRequest(404, { error: 'Not Found' });

    await expect(fetchInvoices()).rejects.toThrow('not found');
  });

  test('throws rate limit error on 429 response', async () => {
    mockHttpsRequest(429, { error: 'Too Many Requests' });

    await expect(fetchInvoices()).rejects.toThrow('rate limit');
  });

  test('throws server error on 500 response', async () => {
    mockHttpsRequest(500, { error: 'Internal Server Error' });

    await expect(fetchInvoices()).rejects.toThrow('server error');
  });

  test('throws network error when request fails', async () => {
    mockHttpsRequest(null, null, new Error('ECONNREFUSED'));

    // Re-mock to emit error on request
    const mockRequest = {
      on: jest.fn((event, handler) => {
        if (event === 'error') handler(new Error('ECONNREFUSED'));
      }),
      setTimeout: jest.fn(),
      destroy: jest.fn(),
      end: jest.fn(),
    };
    https.request.mockImplementation(() => mockRequest);

    await expect(fetchInvoices()).rejects.toThrow('Network error');
  });

  test('throws timeout error when request times out', async () => {
    const mockRequest = {
      on: jest.fn(),
      setTimeout: jest.fn((ms, handler) => handler()), // immediately trigger timeout
      destroy: jest.fn(),
      end: jest.fn(),
    };
    https.request.mockImplementation(() => mockRequest);

    await expect(fetchInvoices()).rejects.toThrow('timed out');
  });

  test('throws config error when access token is missing', async () => {
    delete process.env.FRESHBOOKS_ACCESS_TOKEN;

    await expect(fetchInvoices()).rejects.toThrow('FRESHBOOKS_ACCESS_TOKEN');
  });

  test('throws config error when account ID is missing', async () => {
    delete process.env.FRESHBOOKS_ACCOUNT_ID;

    await expect(fetchInvoices()).rejects.toThrow('FRESHBOOKS_ACCOUNT_ID');
  });

  test('throws parse error on malformed JSON response', async () => {
    mockHttpsRequest(200, 'not valid json {{{}');

    await expect(fetchInvoices()).rejects.toThrow('Failed to parse');
  });

  test('throws error on unexpected response structure', async () => {
    mockHttpsRequest(200, { unexpected: 'structure' });

    await expect(fetchInvoices()).rejects.toThrow('Unexpected FreshBooks API response structure');
  });
});

// ─── normalizeInvoice() Tests ────────────────────────────────────────────────

describe('normalizeInvoice()', () => {
  test('normalizes a complete invoice object', () => {
    const raw = {
      id: 999,
      invoice_number: 'INV-999',
      v3_status: 'draft',
      customerid: 10,
      current_organization: 'Test Co',
      amount: { amount: '500.00', code: 'CAD' },
      outstanding: { amount: '500.00', code: 'CAD' },
      create_date: '2024-03-01',
      due_date: '2024-04-01',
      description: 'Test invoice',
      lines: [
        {
          lineid: 5,
          description: 'Item A',
          qty: 2,
          unit_cost: { amount: '250.00' },
          amount: { amount: '500.00' },
        },
      ],
    };

    const normalized = normalizeInvoice(raw);

    expect(normalized.id).toBe(999);
    expect(normalized.invoiceNumber).toBe('INV-999');
    expect(normalized.status).toBe('draft');
    expect(normalized.clientId).toBe(10);
    expect(normalized.clientName).toBe('Test Co');
    expect(normalized.amount.total).toBe('500.00');
    expect(normalized.amount.currency).toBe('CAD');
    expect(normalized.lines).toHaveLength(1);
    expect(normalized.lines[0].id).toBe(5);
    expect(normalized.lines[0].quantity).toBe(2);
  });

  test('handles missing optional fields gracefully', () => {
    const raw = { id: 1 };
    const normalized = normalizeInvoice(raw);

    expect(normalized.id).toBe(1);
    expect(normalized.invoiceNumber).toBe('');
    expect(normalized.status).toBe('unknown');
    expect(normalized.clientName).toBe('Unknown Client');
    expect(normalized.amount.total).toBe('0.00');
    expect(normalized.amount.currency).toBe('USD');
    expect(normalized.lines).toEqual([]);
  });

  test('falls back to invoiceid when id is not present', () => {
    const raw = { invoiceid: 777 };
    const normalized = normalizeInvoice(raw);
    expect(normalized.id).toBe(777);
  });
});
