const csvParser = require('../services/csvParser');
const Transaction = require('../models/Transaction');
const fs = require('fs');

/**
 * POST /api/finance/upload-csv
 * Accepts a multipart/form-data request with a CSV file field named "file".
 * Parses the CSV, stores transactions in SQLite, and returns the results.
 */
exports.uploadCsv = async (req, res) => {
  // Ensure a file was actually attached
  if (!req.file) {
    return res.status(400).json({ error: 'No file uploaded. Please attach a CSV file with field name "file".' });
  }

  const filePath = req.file.path;

  try {
    // Parse the uploaded CSV file into transaction objects
    const transactions = await csvParser.parseCsv(req.file);

    if (transactions.length === 0) {
      // Clean up the temp file before returning
      cleanupFile(filePath);
      return res.status(200).json({
        message: 'CSV file processed successfully, but no transactions were found.',
        transactions: [],
      });
    }

    // Persist all parsed transactions to the database
    const saved = await Transaction.bulkCreate(transactions);

    // Clean up the uploaded temp file after successful processing
    cleanupFile(filePath);

    return res.status(200).json({
      message: 'CSV file processed successfully',
      count: saved.length,
      transactions: saved,
    });
  } catch (error) {
    // Always attempt to clean up the temp file on error
    cleanupFile(filePath);

    // Distinguish between parsing errors and DB errors for clearer messages
    const statusCode = error.name === 'CsvParseError' ? 422 : 400;
    return res.status(statusCode).json({ error: error.message });
  }
};

/**
 * Safely removes a file from disk, ignoring errors if the file no longer exists.
 * @param {string} filePath - Absolute path to the file to remove.
 */
function cleanupFile(filePath) {
  if (!filePath) return;
  fs.unlink(filePath, (err) => {
    if (err && err.code !== 'ENOENT') {
      console.error(`[financeController] Failed to clean up temp file ${filePath}:`, err.message);
    }
  });
}
