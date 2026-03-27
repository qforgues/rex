'use strict';

/**
 * Unit Tests for csvNormalizer service
 * Tests parsing, normalization, date handling, amount handling, and edge cases.
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

const {
  normalizeCSV,
  normalizeHeader,
  buildHeaderMap,
  parseDate,
  parseAmount,
  normalizeRow,
  validateRow
} = require('./csvNormalizer');

// ---------------------------------------------------------------------------
// Helper: Write a temp CSV file and return its path
// ---------------------------------------------------------------------------
function writeTempCSV(content) {
  const tmpPath = path.join(os.tmpdir(), `test-csv-${Date.now()}-${Math.random()}.csv`);
  fs.writeFileSync(tmpPath, content, 'utf8');
  return tmpPath;
}

function cleanupFile(filePath) {
  if (fs.existsSync(filePath)) {
    fs.unlinkSync(filePath);
  }
}

// ---------------------------------------------------------------------------
// normalizeHeader
// ---------------------------------------------------------------------------
describe('normalizeHeader', () => {
  test('converts to lowercase', () => {
    expect(normalizeHeader('Date')).toBe('date');
    expect(normalizeHeader('TRANSACTION DATE')).toBe('transaction date');
  });

  test('trims whitespace', () => {
    expect(normalizeHeader('  amount  ')).toBe('amount');
  });

  test('removes special characters', () => {
    expect(normalizeHeader('Amount ($)')).toBe('amount ');
  });
});

// ---------------------------------------------------------------------------
// buildHeaderMap
// ---------------------------------------------------------------------------
describe('buildHeaderMap', () => {
  test('maps standard headers correctly', () => {
    const headers = ['Date', 'Description', 'Amount', 'Balance'];
    const map = buildHeaderMap(headers);
    expect(map['Date']).toBe('date');
    expect(map['Description']).toBe('description');
    expect(map['Amount']).toBe('amount');
    expect(map['Balance']).toBe('balance');
  });

  test('maps alternative header names', () => {
    const headers = ['Transaction Date', 'Memo', 'Debit', 'Credit'];
    const map = buildHeaderMap(headers);
    expect(map['Transaction Date']).toBe('date');
    expect(map['Memo']).toBe('description');
    expect(map['Debit']).toBe('debit');
    expect(map['Credit']).toBe('credit');
  });

  test('handles unknown headers as custom fields', () => {
    const headers = ['CustomField', 'Another Field'];
    const map = buildHeaderMap(headers);
    expect(map['CustomField']).toBe('customfield');
    expect(map['Another Field']).toBe('another_field');
  });

  test('handles empty headers array', () => {
    const map = buildHeaderMap([]);
    expect(Object.keys(map)).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// parseDate
// ---------------------------------------------------------------------------
describe('parseDate', () => {
  test('parses ISO 8601 date', () => {
    const d = parseDate('2024-01-15');
    expect(d).toBeInstanceOf(Date);
    expect(d.getFullYear()).toBe(2024);
    expect(d.getMonth()).toBe(0); // January
    expect(d.getDate()).toBe(15);
  });

  test('parses MM/DD/YYYY format', () => {
    const d = parseDate('01/15/2024');
    expect(d).toBeInstanceOf(Date);
    expect(d.getFullYear()).toBe(2024);
  });

  test('parses DD/MM/YYYY format', () => {
    const d = parseDate('15/01/2024');
    expect(d).toBeInstanceOf(Date);
  });

  test('parses date with dashes DD-MM-YYYY', () => {
    const d = parseDate('15-01-2024');
    expect(d).toBeInstanceOf(Date);
  });

  test('parses MM/DD/YY short year', () => {
    const d = parseDate('01/15/24');
    expect(d).toBeInstanceOf(Date);
    expect(d.getFullYear()).toBe(2024);
  });

  test('returns null for empty string', () => {
    expect(parseDate('')).toBeNull();
  });

  test('returns null for null input', () => {
    expect(parseDate(null)).toBeNull();
  });

  test('returns null for invalid date string', () => {
    expect(parseDate('not-a-date')).toBeNull();
  });

  test('returns null for undefined', () => {
    expect(parseDate(undefined)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// parseAmount
// ---------------------------------------------------------------------------
describe('parseAmount', () => {
  test('parses plain number string', () => {
    expect(parseAmount('100.50')).toBe(100.50);
  });

  test('parses negative amount', () => {
    expect(parseAmount('-50.25')).toBe(-50.25);
  });

  test('parses amount with dollar sign', () => {
    expect(parseAmount('$1,234.56')).toBe(1234.56);
  });

  test('parses amount with euro sign', () => {
    expect(parseAmount('€500.00')).toBe(500.00);
  });

  test('parses amount with pound sign', () => {
    expect(parseAmount('£75.99')).toBe(75.99);
  });

  test('parses accounting negative (parentheses)', () => {
    expect(parseAmount('(200.00)')).toBe(-200.00);
  });

  test('parses amount with commas as thousands separator', () => {
    expect(parseAmount('1,000,000.00')).toBe(1000000.00);
  });

  test('returns null for empty string', () => {
    expect(parseAmount('')).toBeNull();
  });

  test('returns null for null', () => {
    expect(parseAmount(null)).toBeNull();
  });

  test('returns null for non-numeric string', () => {
    expect(parseAmount('N/A')).toBeNull();
  });

  test('handles numeric input directly', () => {
    expect(parseAmount(42.5)).toBe(42.5);
  });

  test('parses zero', () => {
    expect(parseAmount('0.00')).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// normalizeRow
// ---------------------------------------------------------------------------
describe('normalizeRow', () => {
  const headerMap = {
    'Date': 'date',
    'Description': 'description',
    'Amount': 'amount',
    'Balance': 'balance'
  };

  test('normalizes a standard row', () => {
    const row = {
      'Date': '2024-01-15',
      'Description': 'Coffee Shop',
      'Amount': '-5.50',
      'Balance': '994.50'
    };
    const result = normalizeRow(row, headerMap);
    expect(result.date).toBeInstanceOf(Date);
    expect(result.description).toBe('Coffee Shop');
    expect(result.amount).toBe(-5.50);
    expect(result.balance).toBe(994.50);
    expect(result.rawData).toEqual(row);
  });

  test('computes amount from debit/credit columns', () => {
    const debitCreditHeaderMap = {
      'Date': 'date',
      'Description': 'description',
      'Debit': 'debit',
      'Credit': 'credit'
    };
    const row = {
      'Date': '2024-01-15',
      'Description': 'Salary',
      'Debit': '',
      'Credit': '3000.00'
    };
    const result = normalizeRow(row, debitCreditHeaderMap);
    expect(result.amount).toBe(3000.00);
  });

  test('computes negative amount from debit only', () => {
    const debitCreditHeaderMap = {
      'Date': 'date',
      'Description': 'description',
      'Debit': 'debit',
      'Credit': 'credit'
    };
    const row = {
      'Date': '2024-01-15',
      'Description': 'Rent',
      'Debit': '1500.00',
      'Credit': ''
    };
    const result = normalizeRow(row, debitCreditHeaderMap);
    expect(result.amount).toBe(-1500.00);
  });

  test('preserves rawData', () => {
    const row = { 'Date': '2024-01-15', 'Description': 'Test', 'Amount': '10.00', 'Balance': '100.00' };
    const result = normalizeRow(row, headerMap);
    expect(result.rawData).toEqual(row);
  });
});

// ---------------------------------------------------------------------------
// validateRow
// ---------------------------------------------------------------------------
describe('validateRow', () => {
  test('valid row passes validation', () => {
    const row = {
      date: new Date(),
      amount: -50,
      description: 'Test'
    };
    const { valid, warnings } = validateRow(row, 1);
    expect(valid).toBe(true);
    expect(warnings).toHaveLength(0);
  });

  test('row missing date is invalid', () => {
    const row = { date: null, amount: -50, description: 'Test' };
    const { valid, warnings } = validateRow(row, 2);
    expect(valid).toBe(false);
    expect(warnings.some(w => w.includes('date'))).toBe(true);
  });

  test('row missing amount is invalid', () => {
    const row = { date: new Date(), amount: null, description: 'Test' };
    const { valid, warnings } = validateRow(row, 3);
    expect(valid).toBe(false);
    expect(warnings.some(w => w.includes('amount'))).toBe(true);
  });

  test('row missing description generates warning but may still be valid', () => {
    const row = { date: new Date(), amount: -10, description: null };
    const { valid, warnings } = validateRow(row, 4);
    expect(valid).toBe(true); // date and amount present
    expect(warnings.some(w => w.includes('description'))).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// normalizeCSV (integration-style tests using temp files)
// ---------------------------------------------------------------------------
describe('normalizeCSV', () => {
  let tempFiles = [];

  afterEach(() => {
    // Clean up temp files after each test
    tempFiles.forEach(cleanupFile);
    tempFiles = [];
  });

  test('parses a standard bank CSV format', async () => {
    const content = [
      'Date,Description,Amount,Balance',
      '2024-01-01,Opening Balance,0.00,1000.00',
      '2024-01-02,Coffee Shop,-5.50,994.50',
      '2024-01-03,Salary,3000.00,3994.50'
    ].join('\n');

    const tmpPath = writeTempCSV(content);
    tempFiles.push(tmpPath);

    const result = await normalizeCSV(tmpPath);
    expect(result.data).toHaveLength(3);
    expect(result.data[0].description).toBe('Opening Balance');
    expect(result.data[1].amount).toBe(-5.50);
    expect(result.data[2].amount).toBe(3000.00);
  });

  test('parses debit/credit split column format', async () => {
    const content = [
      'Date,Description,Debit,Credit,Balance',
      '2024-01-02,Grocery Store,85.00,,914.50',
      '2024-01-03,Paycheck,,2500.00,3414.50'
    ].join('\n');

    const tmpPath = writeTempCSV(content);
    tempFiles.push(tmpPath);

    const result = await normalizeCSV(tmpPath);
    expect(result.data).toHaveLength(2);
    expect(result.data[0].amount).toBe(-85.00);
    expect(result.data[1].amount).toBe(2500.00);
  });

  test('handles alternative header names (Memo, Transaction Date)', async () => {
    const content = [
      'Transaction Date,Memo,Amount',
      '01/15/2024,ATM Withdrawal,-200.00',
      '01/16/2024,Direct Deposit,1500.00'
    ].join('\n');

    const tmpPath = writeTempCSV(content);
    tempFiles.push(tmpPath);

    const result = await normalizeCSV(tmpPath);
    expect(result.data).toHaveLength(2);
    expect(result.data[0].description).toBe('ATM Withdrawal');
  });

  test('skips rows with missing date and amount', async () => {
    const content = [
      'Date,Description,Amount',
      '2024-01-01,Valid Transaction,-10.00',
      ',No Date Row,',
      '2024-01-03,Another Valid,20.00'
    ].join('\n');

    const tmpPath = writeTempCSV(content);
    tempFiles.push(tmpPath);

    const result = await normalizeCSV(tmpPath);
    expect(result.data).toHaveLength(2);
    expect(result.skipped).toBe(1);
  });

  test('returns warnings for problematic rows', async () => {
    const content = [
      'Date,Description,Amount',
      '2024-01-01,Valid,-10.00',
      ',Missing Date,-5.00'
    ].join('\n');

    const tmpPath = writeTempCSV(content);
    tempFiles.push(tmpPath);

    const result = await normalizeCSV(tmpPath);
    expect(result.warnings.length).toBeGreaterThan(0);
  });

  test('rejects empty file', async () => {
    const tmpPath = path.join(os.tmpdir(), `empty-${Date.now()}.csv`);
    fs.writeFileSync(tmpPath, '', 'utf8');
    tempFiles.push(tmpPath);

    await expect(normalizeCSV(tmpPath)).rejects.toThrow('empty');
  });

  test('rejects non-existent file', async () => {
    await expect(normalizeCSV('/nonexistent/path/file.csv')).rejects.toThrow('File not found');
  });

  test('rejects null file path', async () => {
    await expect(normalizeCSV(null)).rejects.toThrow('Invalid file path');
  });

  test('handles CSV with extra whitespace in values', async () => {
    const content = [
      'Date,Description,Amount',
      '2024-01-01,  Padded Description  ,  -15.00  '
    ].join('\n');

    const tmpPath = writeTempCSV(content);
    tempFiles.push(tmpPath);

    const result = await normalizeCSV(tmpPath);
    expect(result.data[0].description).toBe('Padded Description');
    expect(result.data[0].amount).toBe(-15.00);
  });

  test('handles CSV with currency symbols in amounts', async () => {
    const content = [
      'Date,Description,Amount',
      '2024-01-01,Purchase,$1,234.56',
      '2024-01-02,Refund,£50.00'
    ].join('\n');

    const tmpPath = writeTempCSV(content);
    tempFiles.push(tmpPath);

    const result = await normalizeCSV(tmpPath);
    expect(result.data[0].amount).toBe(1234.56);
    expect(result.data[1].amount).toBe(50.00);
  });

  test('handles CSV with only headers and no data rows', async () => {
    const content = 'Date,Description,Amount\n';
    const tmpPath = writeTempCSV(content);
    tempFiles.push(tmpPath);

    await expect(normalizeCSV(tmpPath)).rejects.toThrow();
  });

  test('preserves rawData for each row', async () => {
    const content = [
      'Date,Description,Amount',
      '2024-01-01,Test Transaction,-25.00'
    ].join('\n');

    const tmpPath = writeTempCSV(content);
    tempFiles.push(tmpPath);

    const result = await normalizeCSV(tmpPath);
    expect(result.data[0].rawData).toBeDefined();
    expect(result.data[0].rawData['Description']).toBe('Test Transaction');
  });
});
