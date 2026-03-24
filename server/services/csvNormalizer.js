'use strict';

/**
 * CSV Normalization Service
 * Handles parsing and normalizing CSV files from various bank and credit card formats.
 * Standardizes data into a consistent format for storage and processing.
 */

const fs = require('fs');
const path = require('path');
const csv = require('fast-csv');

/**
 * Known column mappings for various bank/credit card CSV formats.
 * Maps common header variations to our standardized field names.
 */
const COLUMN_MAPPINGS = {
  // Date field variations
  date: [
    'date', 'transaction date', 'trans date', 'posted date',
    'posting date', 'value date', 'settlement date', 'trans_date',
    'transaction_date', 'posted_date'
  ],
  // Description field variations
  description: [
    'description', 'memo', 'narrative', 'details', 'transaction description',
    'merchant name', 'payee', 'reference', 'particulars', 'trans description',
    'transaction_description', 'merchant'
  ],
  // Amount field variations
  amount: [
    'amount', 'transaction amount', 'debit/credit', 'value',
    'trans amount', 'transaction_amount', 'net amount'
  ],
  // Debit field variations (some banks split debit/credit)
  debit: [
    'debit', 'withdrawal', 'debit amount', 'withdrawals',
    'debit_amount', 'money out'
  ],
  // Credit field variations
  credit: [
    'credit', 'deposit', 'credit amount', 'deposits',
    'credit_amount', 'money in'
  ],
  // Balance field variations
  balance: [
    'balance', 'running balance', 'available balance',
    'closing balance', 'account balance'
  ],
  // Category field variations
  category: [
    'category', 'type', 'transaction type', 'trans type',
    'transaction_type', 'mcc', 'merchant category'
  ],
  // Reference/ID field variations
  reference: [
    'reference', 'reference number', 'transaction id', 'trans id',
    'check number', 'cheque number', 'ref', 'transaction_id'
  ]
};

/**
 * Normalizes a header string for comparison.
 * Converts to lowercase and trims whitespace.
 * @param {string} header - Raw header string
 * @returns {string} Normalized header
 */
function normalizeHeader(header) {
  return header.toLowerCase().trim().replace(/[^a-z0-9\s_]/g, '');
}

/**
 * Maps raw CSV headers to standardized field names.
 * @param {string[]} rawHeaders - Array of raw header strings from CSV
 * @returns {Object} Mapping of raw header -> standardized field name
 */
function buildHeaderMap(rawHeaders) {
  const headerMap = {};

  rawHeaders.forEach((rawHeader) => {
    const normalized = normalizeHeader(rawHeader);

    // Check each standardized field's known variations
    for (const [standardField, variations] of Object.entries(COLUMN_MAPPINGS)) {
      if (variations.includes(normalized)) {
        headerMap[rawHeader] = standardField;
        break;
      }
    }

    // If no mapping found, keep the original (lowercased) as a custom field
    if (!headerMap[rawHeader]) {
      headerMap[rawHeader] = normalized.replace(/\s+/g, '_');
    }
  });

  return headerMap;
}

/**
 * Parses a date string into a JavaScript Date object.
 * Handles multiple common date formats.
 * @param {string} dateStr - Raw date string
 * @returns {Date|null} Parsed date or null if unparseable
 */
function parseDate(dateStr) {
  if (!dateStr || typeof dateStr !== 'string') return null;

  const trimmed = dateStr.trim();
  if (!trimmed) return null;

  // Try native Date parsing first (handles ISO 8601 and many common formats)
  const nativeDate = new Date(trimmed);
  if (!isNaN(nativeDate.getTime())) {
    return nativeDate;
  }

  // Try DD/MM/YYYY format
  const ddmmyyyy = trimmed.match(/^(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})$/);
  if (ddmmyyyy) {
    const [, day, month, year] = ddmmyyyy;
    const d = new Date(`${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`);
    if (!isNaN(d.getTime())) return d;
  }

  // Try MM/DD/YY format
  const mmddyy = trimmed.match(/^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2})$/);
  if (mmddyy) {
    const [, month, day, year] = mmddyy;
    const fullYear = parseInt(year) > 50 ? `19${year}` : `20${year}`;
    const d = new Date(`${fullYear}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`);
    if (!isNaN(d.getTime())) return d;
  }

  return null;
}

/**
 * Parses an amount string into a float.
 * Handles currency symbols, parentheses for negatives, and various separators.
 * @param {string} amountStr - Raw amount string
 * @returns {number|null} Parsed amount or null if unparseable
 */
function parseAmount(amountStr) {
  if (amountStr === null || amountStr === undefined) return null;
  if (typeof amountStr === 'number') return amountStr;

  const str = String(amountStr).trim();
  if (!str) return null;

  // Remove currency symbols and whitespace
  let cleaned = str.replace(/[\$£€¥₹,\s]/g, '');

  // Handle parentheses as negative (e.g., accounting format)
  const isNegative = cleaned.startsWith('(') && cleaned.endsWith(')');
  if (isNegative) {
    cleaned = '-' + cleaned.slice(1, -1);
  }

  // Handle explicit negative sign with currency symbol
  cleaned = cleaned.replace(/^-\s*/, '-');

  const parsed = parseFloat(cleaned);
  return isNaN(parsed) ? null : parsed;
}

/**
 * Normalizes a single CSV row using the header map.
 * @param {Object} rawRow - Raw row object from CSV parser
 * @param {Object} headerMap - Mapping of raw headers to standardized fields
 * @returns {Object} Normalized transaction object
 */
function normalizeRow(rawRow, headerMap) {
  const normalized = {
    date: null,
    description: null,
    amount: null,
    debit: null,
    credit: null,
    balance: null,
    category: null,
    reference: null,
    rawData: {} // Preserve original data for audit purposes
  };

  // Store raw data for audit trail
  normalized.rawData = { ...rawRow };

  // Map each raw field to its standardized equivalent
  for (const [rawHeader, standardField] of Object.entries(headerMap)) {
    const rawValue = rawRow[rawHeader];

    switch (standardField) {
      case 'date':
        normalized.date = parseDate(rawValue);
        break;
      case 'description':
        normalized.description = rawValue ? String(rawValue).trim() : null;
        break;
      case 'amount':
        normalized.amount = parseAmount(rawValue);
        break;
      case 'debit':
        normalized.debit = parseAmount(rawValue);
        break;
      case 'credit':
        normalized.credit = parseAmount(rawValue);
        break;
      case 'balance':
        normalized.balance = parseAmount(rawValue);
        break;
      case 'category':
        normalized.category = rawValue ? String(rawValue).trim() : null;
        break;
      case 'reference':
        normalized.reference = rawValue ? String(rawValue).trim() : null;
        break;
      default:
        // Store unmapped fields as custom properties
        if (rawValue !== undefined && rawValue !== null && rawValue !== '') {
          normalized[standardField] = rawValue;
        }
    }
  }

  // If amount is null but debit/credit are present, compute amount
  if (normalized.amount === null) {
    const debit = normalized.debit;
    const credit = normalized.credit;

    if (debit !== null && credit !== null) {
      // Net amount: credit is positive, debit is negative
      normalized.amount = (credit || 0) - (debit || 0);
    } else if (debit !== null) {
      normalized.amount = -Math.abs(debit);
    } else if (credit !== null) {
      normalized.amount = Math.abs(credit);
    }
  }

  return normalized;
}

/**
 * Validates that a normalized row has the minimum required fields.
 * @param {Object} row - Normalized row object
 * @param {number} rowIndex - Row index for error reporting
 * @returns {{ valid: boolean, warnings: string[] }}
 */
function validateRow(row, rowIndex) {
  const warnings = [];

  if (!row.date) {
    warnings.push(`Row ${rowIndex}: Missing or unparseable date`);
  }

  if (row.amount === null) {
    warnings.push(`Row ${rowIndex}: Missing or unparseable amount`);
  }

  if (!row.description) {
    warnings.push(`Row ${rowIndex}: Missing description`);
  }

  return {
    valid: row.date !== null && row.amount !== null,
    warnings
  };
}

/**
 * Main normalization function.
 * Reads a CSV file from the given filePath, normalizes the data into a
 * consistent format, and returns a promise resolving to an array of
 * normalized data objects.
 *
 * @param {string} filePath - Absolute or relative path to the CSV file
 * @returns {Promise<{ data: Object[], warnings: string[], skipped: number }>}
 */
function normalizeCSV(filePath) {
  return new Promise((resolve, reject) => {
    // Validate file exists and is accessible
    if (!filePath || typeof filePath !== 'string') {
      return reject(new Error('Invalid file path provided'));
    }

    const absolutePath = path.resolve(filePath);

    if (!fs.existsSync(absolutePath)) {
      return reject(new Error(`File not found: ${absolutePath}`));
    }

    const stats = fs.statSync(absolutePath);
    if (stats.size === 0) {
      return reject(new Error('CSV file is empty'));
    }

    const results = [];
    const allWarnings = [];
    let headerMap = null;
    let rowIndex = 0;
    let skipped = 0;
    let hasData = false;

    const stream = fs.createReadStream(absolutePath, { encoding: 'utf8' });

    // Handle stream errors (e.g., permission denied)
    stream.on('error', (err) => {
      reject(new Error(`Failed to read file: ${err.message}`));
    });

    const parser = csv.parse({
      headers: true,          // Use first row as headers
      trim: true,             // Trim whitespace from values
      skipEmptyLines: true,   // Skip blank lines
      ignoreEmpty: false,     // Don't silently drop empty fields
      strictColumnHandling: false // Allow rows with different column counts
    });

    parser.on('error', (err) => {
      reject(new Error(`CSV parsing error: ${err.message}`));
    });

    parser.on('headers', (headers) => {
      if (!headers || headers.length === 0) {
        parser.destroy();
        return reject(new Error('CSV file has no headers'));
      }

      // Check for completely empty headers
      const nonEmptyHeaders = headers.filter(h => h && h.trim());
      if (nonEmptyHeaders.length === 0) {
        parser.destroy();
        return reject(new Error('CSV file headers are all empty'));
      }

      headerMap = buildHeaderMap(headers);
    });

    parser.on('data', (row) => {
      rowIndex++;
      hasData = true;

      // Skip rows that are entirely empty
      const values = Object.values(row);
      if (values.every(v => !v || !String(v).trim())) {
        skipped++;
        return;
      }

      const normalized = normalizeRow(row, headerMap);
      const { valid, warnings } = validateRow(normalized, rowIndex);

      // Collect warnings but don't reject valid-enough rows
      allWarnings.push(...warnings);

      if (valid) {
        results.push(normalized);
      } else {
        skipped++;
        allWarnings.push(`Row ${rowIndex}: Skipped due to missing required fields (date and amount)`);
      }
    });

    parser.on('end', () => {
      if (!hasData) {
        return reject(new Error('CSV file contains no data rows'));
      }

      resolve({
        data: results,
        warnings: allWarnings,
        skipped
      });
    });

    // Pipe file stream into CSV parser
    stream.pipe(parser);
  });
}

module.exports = {
  normalizeCSV,
  // Export helpers for unit testing
  normalizeHeader,
  buildHeaderMap,
  parseDate,
  parseAmount,
  normalizeRow,
  validateRow
};
