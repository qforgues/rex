/**
 * Unit tests for the CSV parsing service.
 * Uses Jest and temporary files to simulate real uploads.
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { parseCsv, CsvParseError } = require('../../server/services/csvParser');

/**
 * Helper: writes content to a temp file and returns a multer-like file object.
 * @param {string} content
 * @param {string} [filename]
 * @returns {{ path: string, originalname: string }}
 */
function createTempFile(content, filename = 'test.csv') {
  const tmpPath = path.join(os.tmpdir(), `${Date.now()}-${filename}`);
  fs.writeFileSync(tmpPath, content, 'utf8');
  return { path: tmpPath, originalname: filename };
}

/**
 * Helper: removes a temp file if it exists.
 */
function removeTempFile(filePath) {
  if (filePath && fs.existsSync(filePath)) {
    fs.unlinkSync(filePath);
  }
}

describe('csvParser.parseCsv', () => {
  // ── Happy path ──────────────────────────────────────────────────────────────

  test('parses a well-formed CSV with all columns', async () => {
    const content = [
      'Date,Description,Amount,Category',
      '2024-01-15,Coffee Shop,-4.50,Food',
      '2024-01-16,Salary,3000.00,Income',
    ].join('\n');

    const file = createTempFile(content);
    try {
      const transactions = await parseCsv(file);
      expect(transactions).toHaveLength(2);
      expect(transactions[0]).toEqual({
        date: '2024-01-15',
        description: 'Coffee Shop',
        amount: -4.5,
        category: 'Food',
      });
      expect(transactions[1]).toEqual({
        date: '2024-01-16',
        description: 'Salary',
        amount: 3000.0,
        category: 'Income',
      });
    } finally {
      removeTempFile(file.path);
    }
  });

  test('parses a CSV without the optional Category column', async () => {
    const content = [
      'Date,Description,Amount',
      '2024-02-01,Rent,-1200.00',
    ].join('\n');

    const file = createTempFile(content);
    try {
      const transactions = await parseCsv(file);
      expect(transactions).toHaveLength(1);
      expect(transactions[0].category).toBeNull();
    } finally {
      removeTempFile(file.path);
    }
  });

  test('handles headers with mixed case', async () => {
    const content = [
      'DATE,DESCRIPTION,AMOUNT,CATEGORY',
      '2024-03-10,Gym,-50.00,Health',
    ].join('\n');

    const file = createTempFile(content);
    try {
      const transactions = await parseCsv(file);
      expect(transactions).toHaveLength(1);
      expect(transactions[0].amount).toBe(-50);
    } finally {
      removeTempFile(file.path);
    }
  });

  test('strips currency symbols from amount', async () => {
    const content = [
      'Date,Description,Amount',
      '2024-04-01,Groceries,$-75.30',
    ].join('\n');

    const file = createTempFile(content);
    try {
      const transactions = await parseCsv(file);
      expect(transactions[0].amount).toBe(-75.3);
    } finally {
      removeTempFile(file.path);
    }
  });

  test('skips completely empty rows', async () => {
    const content = [
      'Date,Description,Amount,Category',
      '2024-05-01,Taxi,-12.00,Transport',
      ',,, ',
      '2024-05-02,Bus,-2.50,Transport',
    ].join('\n');

    const file = createTempFile(content);
    try {
      const transactions = await parseCsv(file);
      expect(transactions).toHaveLength(2);
    } finally {
      removeTempFile(file.path);
    }
  });

  test('returns empty array for a CSV with only headers', async () => {
    const content = 'Date,Description,Amount,Category\n';
    const file = createTempFile(content);
    try {
      const transactions = await parseCsv(file);
      expect(transactions).toHaveLength(0);
    } finally {
      removeTempFile(file.path);
    }
  });

  // ── Error cases ─────────────────────────────────────────────────────────────

  test('throws CsvParseError when required columns are missing', async () => {
    const content = [
      'Date,Notes',
      '2024-06-01,Something',
    ].join('\n');

    const file = createTempFile(content);
    try {
      await expect(parseCsv(file)).rejects.toThrow(CsvParseError);
      await expect(parseCsv(file)).rejects.toThrow(/missing required column/);
    } finally {
      removeTempFile(file.path);
    }
  });

  test('throws CsvParseError when Amount is not a number', async () => {
    const content = [
      'Date,Description,Amount',
      '2024-07-01,Bad Row,not-a-number',
    ].join('\n');

    const file = createTempFile(content);
    try {
      await expect(parseCsv(file)).rejects.toThrow(CsvParseError);
      await expect(parseCsv(file)).rejects.toThrow(/not a valid number/);
    } finally {
      removeTempFile(file.path);
    }
  });

  test('throws CsvParseError when Date field is empty', async () => {
    const content = [
      'Date,Description,Amount',
      ',Missing Date,-10.00',
    ].join('\n');

    const file = createTempFile(content);
    try {
      await expect(parseCsv(file)).rejects.toThrow(CsvParseError);
      await expect(parseCsv(file)).rejects.toThrow(/"Date" field is empty/);
    } finally {
      removeTempFile(file.path);
    }
  });

  test('throws CsvParseError when file does not exist', async () => {
    const fakeFile = { path: '/tmp/nonexistent-file-xyz.csv', originalname: 'fake.csv' };
    await expect(parseCsv(fakeFile)).rejects.toThrow(CsvParseError);
    await expect(parseCsv(fakeFile)).rejects.toThrow(/File not found/);
  });

  test('throws CsvParseError when no file object is provided', async () => {
    await expect(parseCsv(null)).rejects.toThrow(CsvParseError);
  });
});
