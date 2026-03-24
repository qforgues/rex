const db = require('../../config/db');

/**
 * Transaction model.
 * Provides methods to interact with the `transactions` table in SQLite.
 *
 * Schema:
 *   id          INTEGER PRIMARY KEY AUTOINCREMENT
 *   date        TEXT    NOT NULL   -- ISO date string or original date text from CSV
 *   description TEXT    NOT NULL
 *   amount      REAL    NOT NULL   -- Positive = credit, Negative = debit
 *   category    TEXT               -- Optional category label
 *   created_at  TEXT    NOT NULL   -- ISO timestamp of insertion
 */

/**
 * Ensures the `transactions` table exists in the database.
 * Called once at module load time.
 */
function initTable() {
  const sql = `
    CREATE TABLE IF NOT EXISTS transactions (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      date        TEXT    NOT NULL,
      description TEXT    NOT NULL,
      amount      REAL    NOT NULL,
      category    TEXT,
      created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
    )
  `;
  // db.run is synchronous in better-sqlite3; use db.exec for DDL
  try {
    db.exec(sql);
  } catch (err) {
    console.error('[Transaction] Failed to initialise transactions table:', err.message);
    throw err;
  }
}

// Initialise the table when the module is first required
initTable();

/**
 * Inserts a single transaction record.
 *
 * @param {{ date: string, description: string, amount: number, category?: string|null }} transaction
 * @returns {{ id: number, date: string, description: string, amount: number, category: string|null, created_at: string }}
 */
function create(transaction) {
  const { date, description, amount, category = null } = transaction;

  if (!date || typeof date !== 'string') {
    throw new Error('Transaction.create: "date" must be a non-empty string.');
  }
  if (!description || typeof description !== 'string') {
    throw new Error('Transaction.create: "description" must be a non-empty string.');
  }
  if (typeof amount !== 'number' || isNaN(amount)) {
    throw new Error('Transaction.create: "amount" must be a valid number.');
  }

  const stmt = db.prepare(`
    INSERT INTO transactions (date, description, amount, category)
    VALUES (@date, @description, @amount, @category)
  `);

  const info = stmt.run({ date, description, amount, category });

  return findById(info.lastInsertRowid);
}

/**
 * Inserts multiple transaction records in a single database transaction.
 * If any insertion fails the entire batch is rolled back.
 *
 * @param {Array<{ date: string, description: string, amount: number, category?: string|null }>} transactions
 * @returns {Array<{ id: number, date: string, description: string, amount: number, category: string|null, created_at: string }>}
 */
function bulkCreate(transactions) {
  if (!Array.isArray(transactions)) {
    throw new Error('Transaction.bulkCreate: argument must be an array.');
  }
  if (transactions.length === 0) {
    return [];
  }

  const stmt = db.prepare(`
    INSERT INTO transactions (date, description, amount, category)
    VALUES (@date, @description, @amount, @category)
  `);

  // Wrap all inserts in a single SQLite transaction for atomicity and performance
  const insertMany = db.transaction((rows) => {
    const inserted = [];
    for (const row of rows) {
      const { date, description, amount, category = null } = row;

      if (!date || typeof date !== 'string') {
        throw new Error(`Transaction.bulkCreate: "date" must be a non-empty string (got: ${JSON.stringify(date)}).`);
      }
      if (!description || typeof description !== 'string') {
        throw new Error(`Transaction.bulkCreate: "description" must be a non-empty string (got: ${JSON.stringify(description)}).`);
      }
      if (typeof amount !== 'number' || isNaN(amount)) {
        throw new Error(`Transaction.bulkCreate: "amount" must be a valid number (got: ${JSON.stringify(amount)}).`);
      }

      const info = stmt.run({ date, description, amount, category });
      inserted.push(info.lastInsertRowid);
    }
    return inserted;
  });

  const ids = insertMany(transactions);

  // Fetch and return the fully persisted records
  return ids.map((id) => findById(id));
}

/**
 * Retrieves a single transaction by its primary key.
 *
 * @param {number} id
 * @returns {{ id: number, date: string, description: string, amount: number, category: string|null, created_at: string } | undefined}
 */
function findById(id) {
  return db.prepare('SELECT * FROM transactions WHERE id = ?').get(id);
}

/**
 * Retrieves all transactions, ordered by date descending.
 *
 * @returns {Array<{ id: number, date: string, description: string, amount: number, category: string|null, created_at: string }>}
 */
function findAll() {
  return db.prepare('SELECT * FROM transactions ORDER BY date DESC').all();
}

/**
 * Deletes all transactions from the table.
 * Useful for testing and seeding.
 *
 * @returns {number} Number of rows deleted.
 */
function deleteAll() {
  const info = db.prepare('DELETE FROM transactions').run();
  return info.changes;
}

module.exports = {
  create,
  bulkCreate,
  findById,
  findAll,
  deleteAll,
};
