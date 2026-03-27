const csv = require('csv-parser');
const fs = require('fs');
const path = require('path');

/**
 * Custom error class for CSV parsing failures.
 * Allows the controller to distinguish parse errors from other errors.
 */
class CsvParseError extends Error {
  constructor(message) {
    super(message);
    this.name = 'CsvParseError';
  }
}

/**
 * Required columns that must be present in the CSV file (case-insensitive match).
 */
const REQUIRED_COLUMNS = ['date', 'description', 'amount'];

/**
 * Normalises a header string: trims whitespace and converts to lowercase.
 * @param {string} header
 * @returns {string}
 */
function normaliseHeader(header) {
  return header.trim().toLowerCase();
}

/**
 * Validates that all required columns are present in the parsed header set.
 * @param {Set<string>} headerSet - Set of normalised header names.
 * @throws {CsvParseError} if any required column is missing.
 */
function validateHeaders(headerSet) {
  const missing = REQUIRED_COLUMNS.filter((col) => !headerSet.has(col));
  if (missing.length > 0) {
    throw new CsvParseError(
      `CSV is missing required column(s): ${missing.join(', ')}. ` +
        `Expected columns: Date, Description, Amount (and optionally Category).`
    );
  }
}

/**
 * Parses a single CSV row into a transaction object.
 * Returns null if the row should be skipped (e.g. all fields empty).
 *
 * @param {Object} row - Raw row object from csv-parser (keys are original headers).
 * @param {Map<string, string>} headerMap - Maps normalised header -> original header.
 * @param {number} rowIndex - 1-based row index for error messages.
 * @returns {{ date: string, description: string, amount: number, category: string|null } | null}
 */
function parseRow(row, headerMap, rowIndex) {
  // Build a normalised key lookup so we can access columns case-insensitively
  const get = (normKey) => {
    const originalKey = headerMap.get(normKey);
    return originalKey !== undefined ? (row[originalKey] || '').trim() : '';
  };

  const dateRaw = get('date');
  const descriptionRaw = get('description');
  const amountRaw = get('amount');
  const categoryRaw = get('category');

  // Skip completely empty rows
  if (!dateRaw && !descriptionRaw && !amountRaw) {
    return null;
  }

  // Validate date
  if (!dateRaw) {
    throw new CsvParseError(`Row ${rowIndex}: "Date" field is empty.`);
  }

  // Validate description
  if (!descriptionRaw) {
    throw new CsvParseError(`Row ${rowIndex}: "Description" field is empty.`);
  }

  // Validate and parse amount
  if (!amountRaw) {
    throw new CsvParseError(`Row ${rowIndex}: "Amount" field is empty.`);
  }

  // Strip currency symbols and thousands separators before parsing
  const cleanedAmount = amountRaw.replace(/[^0-9.\-]/g, '');
  const amount = parseFloat(cleanedAmount);

  if (isNaN(amount)) {
    throw new CsvParseError(
      `Row ${rowIndex}: "Amount" value "${amountRaw}" is not a valid number.`
    );
  }

  return {
    date: dateRaw,
    description: descriptionRaw,
    amount,
    category: categoryRaw || null,
  };
}

/**
 * Parses an uploaded CSV file and returns an array of transaction objects.
 *
 * @param {Express.Multer.File} file - The multer file object (must have a `path` property).
 * @returns {Promise<Array<{ date: string, description: string, amount: number, category: string|null }>>}
 * @throws {CsvParseError} for invalid CSV structure or data.
 * @throws {Error} for file system errors.
 */
exports.parseCsv = (file) => {
  return new Promise((resolve, reject) => {
    if (!file || !file.path) {
      return reject(new CsvParseError('No file path provided for CSV parsing.'));
    }

    // Verify the file exists before attempting to stream it
    if (!fs.existsSync(file.path)) {
      return reject(new CsvParseError(`File not found at path: ${file.path}`));
    }

    const transactions = [];
    let rowIndex = 0;
    // headerMap: normalised header name -> original header name
    let headerMap = null;
    let headersValidated = false;

    const stream = fs.createReadStream(file.path)
      .pipe(
        csv({
          // Use mapHeaders to capture the original headers while normalising for lookup
          mapHeaders: ({ header }) => header, // keep originals; we normalise manually
          skipEmptyLines: true,
        })
      );

    stream
      .on('headers', (headers) => {
        // Build a map of normalised -> original header names
        headerMap = new Map();
        for (const h of headers) {
          headerMap.set(normaliseHeader(h), h);
        }

        // Validate required columns are present
        try {
          validateHeaders(new Set(headerMap.keys()));
          headersValidated = true;
        } catch (err) {
          stream.destroy(err);
        }
      })
      .on('data', (row) => {
        if (!headersValidated) return; // headers failed validation; stream is being destroyed
        rowIndex++;
        try {
          const transaction = parseRow(row, headerMap, rowIndex);
          if (transaction !== null) {
            transactions.push(transaction);
          }
        } catch (err) {
          // Stop processing on the first bad row
          stream.destroy(err);
        }
      })
      .on('end', () => {
        resolve(transactions);
      })
      .on('error', (error) => {
        // Wrap non-CsvParseError errors so the controller can identify them
        if (error instanceof CsvParseError) {
          reject(error);
        } else {
          reject(new CsvParseError(`Failed to read CSV file: ${error.message}`));
        }
      });
  });
};

// Export the error class so tests and controllers can use it
exports.CsvParseError = CsvParseError;
