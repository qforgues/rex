/**
 * financeService.js
 * Service layer for aggregating financial data from MongoDB.
 * Queries Transactions, Accounts, and Invoices collections to produce
 * comprehensive financial summaries filterable by context.
 */

const mongoose = require('mongoose');
const Transaction = require('../models/Transaction');
const Account = require('../models/Account');
const Invoice = require('../models/Invoice');

/**
 * Valid context values accepted by the aggregation functions.
 */
const VALID_CONTEXTS = ['personal', 'business', 'all'];

/**
 * Aggregates financial data for a given user and context.
 *
 * @param {string} userId  - The authenticated user's MongoDB ObjectId (as string).
 * @param {string} context - Filter context: 'personal', 'business', or 'all'.
 * @returns {Promise<Object>} Aggregated financial summary object.
 * @throws {Error} If userId is missing or context is invalid.
 */
async function aggregateFinancialData(userId, context = 'all') {
  // --- Input validation ---
  if (!userId) {
    throw new Error('userId is required');
  }

  const normalizedContext = context.toLowerCase().trim();
  if (!VALID_CONTEXTS.includes(normalizedContext)) {
    throw new Error(
      `Invalid context "${context}". Must be one of: ${VALID_CONTEXTS.join(', ')}`
    );
  }

  // Convert string id to ObjectId safely
  let userObjectId;
  try {
    userObjectId = new mongoose.Types.ObjectId(userId);
  } catch {
    throw new Error('Invalid userId format');
  }

  // Build the context filter applied to all collections.
  // When context is 'all' we omit the filter so every record is included.
  const contextFilter =
    normalizedContext !== 'all' ? { context: normalizedContext } : {};

  // Run all three aggregation pipelines concurrently for performance.
  const [transactionSummary, accountSummary, invoiceSummary] =
    await Promise.all([
      _aggregateTransactions(userObjectId, contextFilter),
      _aggregateAccounts(userObjectId, contextFilter),
      _aggregateInvoices(userObjectId, contextFilter),
    ]);

  return {
    context: normalizedContext,
    transactions: transactionSummary,
    accounts: accountSummary,
    invoices: invoiceSummary,
    // Convenience top-level figures
    netCashFlow:
      (transactionSummary.totalIncome || 0) -
      (transactionSummary.totalExpenses || 0),
    generatedAt: new Date().toISOString(),
  };
}

// ---------------------------------------------------------------------------
// Private helpers
// ---------------------------------------------------------------------------

/**
 * Aggregates transaction totals (income vs expenses) for the user.
 *
 * @param {mongoose.Types.ObjectId} userObjectId
 * @param {Object} contextFilter
 * @returns {Promise<Object>}
 */
async function _aggregateTransactions(userObjectId, contextFilter) {
  const pipeline = [
    {
      $match: {
        userId: userObjectId,
        ...contextFilter,
      },
    },
    {
      // Group by transaction type (income / expense) and sum amounts
      $group: {
        _id: '$type',
        total: { $sum: '$amount' },
        count: { $sum: 1 },
      },
    },
  ];

  const results = await Transaction.aggregate(pipeline).exec();

  // Normalise the grouped results into a flat summary object
  const summary = {
    totalIncome: 0,
    totalExpenses: 0,
    incomeCount: 0,
    expenseCount: 0,
    recentTransactions: [],
  };

  for (const row of results) {
    if (row._id === 'income') {
      summary.totalIncome = row.total;
      summary.incomeCount = row.count;
    } else if (row._id === 'expense') {
      summary.totalExpenses = row.total;
      summary.expenseCount = row.count;
    }
  }

  // Fetch the 5 most recent transactions for the dashboard feed
  summary.recentTransactions = await Transaction.find({
    userId: userObjectId,
    ...contextFilter,
  })
    .sort({ date: -1 })
    .limit(5)
    .select('description amount type date category')
    .lean()
    .exec();

  return summary;
}

/**
 * Aggregates account balances for the user.
 *
 * @param {mongoose.Types.ObjectId} userObjectId
 * @param {Object} contextFilter
 * @returns {Promise<Object>}
 */
async function _aggregateAccounts(userObjectId, contextFilter) {
  const pipeline = [
    {
      $match: {
        userId: userObjectId,
        ...contextFilter,
      },
    },
    {
      $group: {
        _id: '$type', // e.g. 'checking', 'savings', 'credit'
        totalBalance: { $sum: '$balance' },
        accountCount: { $sum: 1 },
      },
    },
    {
      $sort: { _id: 1 },
    },
  ];

  const grouped = await Account.aggregate(pipeline).exec();

  // Also fetch individual account list for the dashboard
  const accounts = await Account.find({
    userId: userObjectId,
    ...contextFilter,
  })
    .select('name type balance currency institution')
    .lean()
    .exec();

  const totalBalance = grouped.reduce(
    (sum, row) => sum + (row.totalBalance || 0),
    0
  );

  return {
    totalBalance,
    byType: grouped.map((row) => ({
      type: row._id,
      totalBalance: row.totalBalance,
      accountCount: row.accountCount,
    })),
    accounts,
  };
}

/**
 * Aggregates invoice data (outstanding, paid, overdue) for the user.
 *
 * @param {mongoose.Types.ObjectId} userObjectId
 * @param {Object} contextFilter
 * @returns {Promise<Object>}
 */
async function _aggregateInvoices(userObjectId, contextFilter) {
  const now = new Date();

  const pipeline = [
    {
      $match: {
        userId: userObjectId,
        ...contextFilter,
      },
    },
    {
      $group: {
        _id: '$status', // 'paid', 'outstanding', 'overdue', 'draft'
        totalAmount: { $sum: '$amount' },
        count: { $sum: 1 },
      },
    },
  ];

  const grouped = await Invoice.aggregate(pipeline).exec();

  // Fetch overdue invoices (outstanding + dueDate in the past)
  const overdueInvoices = await Invoice.find({
    userId: userObjectId,
    status: { $in: ['outstanding', 'sent'] },
    dueDate: { $lt: now },
    ...contextFilter,
  })
    .select('invoiceNumber clientName amount dueDate status')
    .sort({ dueDate: 1 })
    .lean()
    .exec();

  // Build a keyed summary from the aggregation
  const byStatus = {};
  let totalOutstanding = 0;
  let totalPaid = 0;

  for (const row of grouped) {
    byStatus[row._id] = {
      totalAmount: row.totalAmount,
      count: row.count,
    };
    if (row._id === 'paid') totalPaid = row.totalAmount;
    if (['outstanding', 'sent'].includes(row._id))
      totalOutstanding += row.totalAmount;
  }

  return {
    totalOutstanding,
    totalPaid,
    overdueCount: overdueInvoices.length,
    overdueAmount: overdueInvoices.reduce((s, inv) => s + (inv.amount || 0), 0),
    byStatus,
    overdueInvoices,
  };
}

module.exports = {
  aggregateFinancialData,
  VALID_CONTEXTS,
};
