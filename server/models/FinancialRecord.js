'use strict';

/**
 * FinancialRecord Model
 * Mongoose schema for storing normalized financial transaction records.
 * Sensitive fields are encrypted at rest using AES-256 via mongoose-field-encryption.
 */

const mongoose = require('mongoose');
const { fieldEncryption } = require('mongoose-field-encryption');

/**
 * Encryption secret for AES-256.
 * Must be a 32-character (256-bit) string.
 * In production, this MUST come from a secure secrets manager (e.g., AWS Secrets Manager, Vault).
 */
const ENCRYPTION_SECRET = process.env.FIELD_ENCRYPTION_SECRET;

if (!ENCRYPTION_SECRET && process.env.NODE_ENV === 'production') {
  throw new Error(
    'FIELD_ENCRYPTION_SECRET environment variable is required in production. ' +
    'Set a 32-character secret key.'
  );
}

// Use a fallback only in development/test environments
const encryptionSecret =
  ENCRYPTION_SECRET ||
  'dev-secret-key-32-chars-minimum!!'; // 32 chars — NOT for production use

/**
 * FinancialRecord Schema
 * Stores normalized transaction data from CSV uploads.
 * Encrypted fields: description, amount, balance, rawData
 */
const financialRecordSchema = new mongoose.Schema(
  {
    // Reference to the owning user
    userId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: 'User',
      index: true
      // Note: not strictly required to support unauthenticated dev testing,
      // but should be required in production via application-level validation
    },

    // Optional account identifier (e.g., last 4 digits of account number)
    accountId: {
      type: String,
      trim: true,
      default: null
    },

    // Whether this is a personal or business transaction
    accountType: {
      type: String,
      enum: ['personal', 'business'],
      default: 'personal',
      index: true
    },

    // Name of the bank or financial institution
    source: {
      type: String,
      trim: true,
      default: null
    },

    // Original filename of the uploaded CSV
    originalFilename: {
      type: String,
      trim: true,
      default: null
    },

    // --- Core Transaction Fields (encrypted) ---

    // Transaction date parsed from CSV
    transactionDate: {
      type: Date,
      index: true
    },

    // Transaction description / merchant name (ENCRYPTED)
    description: {
      type: String,
      trim: true,
      default: null
    },

    // Net transaction amount — negative for debits, positive for credits (ENCRYPTED)
    amount: {
      type: Number,
      default: null
    },

    // Raw debit amount from CSV (if split columns) (ENCRYPTED)
    debit: {
      type: Number,
      default: null
    },

    // Raw credit amount from CSV (if split columns) (ENCRYPTED)
    credit: {
      type: Number,
      default: null
    },

    // Account balance after transaction (ENCRYPTED)
    balance: {
      type: Number,
      default: null
    },

    // Transaction category (e.g., 'Groceries', 'Utilities')
    category: {
      type: String,
      trim: true,
      default: null,
      index: true
    },

    // Reference number or transaction ID from the bank
    reference: {
      type: String,
      trim: true,
      default: null
    },

    // Original raw row data preserved for audit purposes (ENCRYPTED)
    rawData: {
      type: mongoose.Schema.Types.Mixed,
      default: null
    },

    // Timestamp when this record was uploaded
    uploadedAt: {
      type: Date,
      default: Date.now,
      index: true
    },

    // Flag for soft deletion
    isDeleted: {
      type: Boolean,
      default: false,
      index: true
    }
  },
  {
    timestamps: true, // Adds createdAt and updatedAt
    collection: 'financialrecords'
  }
);

// ---------------------------------------------------------------------------
// Indexes
// ---------------------------------------------------------------------------

// Compound index for common query patterns
financialRecordSchema.index({ userId: 1, accountType: 1, transactionDate: -1 });
financialRecordSchema.index({ userId: 1, uploadedAt: -1 });
financialRecordSchema.index({ userId: 1, isDeleted: 1, transactionDate: -1 });

// ---------------------------------------------------------------------------
// Field-level AES-256 Encryption
// Encrypts sensitive fields before storing in MongoDB.
// The plugin stores encrypted values as strings with a '__enc_' prefix marker.
// ---------------------------------------------------------------------------
financialRecordSchema.plugin(fieldEncryption, {
  fields: ['description', 'amount', 'debit', 'credit', 'balance', 'rawData'],
  secret: encryptionSecret,
  saltGenerator: (secret) => secret.slice(0, 16) // Use first 16 chars as salt
});

// ---------------------------------------------------------------------------
// Virtual Fields
// ---------------------------------------------------------------------------

/**
 * Virtual: transactionType
 * Derives whether a transaction is a 'debit' or 'credit' based on amount.
 */
financialRecordSchema.virtual('transactionType').get(function () {
  if (this.amount === null || this.amount === undefined) return 'unknown';
  return this.amount < 0 ? 'debit' : 'credit';
});

// ---------------------------------------------------------------------------
// Instance Methods
// ---------------------------------------------------------------------------

/**
 * Returns a sanitized version of the record safe for API responses.
 * Excludes rawData and internal encryption markers.
 */
financialRecordSchema.methods.toSafeObject = function () {
  const obj = this.toObject({ virtuals: true });
  delete obj.rawData;
  delete obj.__v;
  return obj;
};

// ---------------------------------------------------------------------------
// Static Methods
// ---------------------------------------------------------------------------

/**
 * Finds records for a user within a date range.
 * @param {string} userId
 * @param {Date} startDate
 * @param {Date} endDate
 * @param {string} [accountType]
 * @returns {Promise<FinancialRecord[]>}
 */
financialRecordSchema.statics.findByDateRange = function (
  userId,
  startDate,
  endDate,
  accountType
) {
  const filter = {
    userId,
    isDeleted: false,
    transactionDate: { $gte: startDate, $lte: endDate }
  };

  if (accountType) {
    filter.accountType = accountType;
  }

  return this.find(filter).sort({ transactionDate: -1 });
};

/**
 * Soft-deletes a record by ID.
 * @param {string} recordId
 * @returns {Promise<FinancialRecord>}
 */
financialRecordSchema.statics.softDelete = function (recordId) {
  return this.findByIdAndUpdate(
    recordId,
    { isDeleted: true },
    { new: true }
  );
};

// ---------------------------------------------------------------------------
// Pre-save Hook
// ---------------------------------------------------------------------------

/**
 * Pre-save hook: Ensures rawData is serialized to a string if it's an object,
 * since the encryption plugin works best with string values.
 */
financialRecordSchema.pre('save', function (next) {
  if (this.rawData && typeof this.rawData === 'object') {
    // Serialize to JSON string for consistent encryption
    this.rawData = JSON.stringify(this.rawData);
  }
  next();
});

const FinancialRecord = mongoose.model('FinancialRecord', financialRecordSchema);

module.exports = FinancialRecord;
