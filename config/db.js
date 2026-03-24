const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

// Allow the database path to be overridden via environment variable.
// Defaults to a file named `financial_assistant.db` in the project root.
const DB_PATH =
  process.env.DATABASE_PATH ||
  path.join(__dirname, '..', 'financial_assistant.db');

// Ensure the directory for the database file exists
const dbDir = path.dirname(DB_PATH);
if (!fs.existsSync(dbDir)) {
  fs.mkdirSync(dbDir, { recursive: true });
}

/**
 * Singleton better-sqlite3 database instance.
 * better-sqlite3 is synchronous and safe to share across the application.
 */
let db;

try {
  db = new Database(DB_PATH, {
    // Log SQL statements in development for easier debugging
    verbose: process.env.NODE_ENV === 'development' ? console.log : null,
  });

  // Enable WAL mode for better concurrent read performance
  db.pragma('journal_mode = WAL');
  // Enforce foreign key constraints
  db.pragma('foreign_keys = ON');

  console.log(`[db] Connected to SQLite database at: ${DB_PATH}`);
} catch (err) {
  console.error('[db] Failed to open SQLite database:', err.message);
  process.exit(1);
}

module.exports = db;
