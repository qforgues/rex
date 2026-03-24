/**
 * Jest setup file - runs BEFORE test modules are loaded
 * This ensures environment variables are set before any modules require config/db.js
 */

// Set test environment variables
process.env.NODE_ENV = 'test';

// Use in-memory database for all tests
// better-sqlite3 treats ':memory:' as an in-memory database
process.env.DATABASE_PATH = ':memory:';
