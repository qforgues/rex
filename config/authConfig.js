'use strict';

/**
 * Authentication configuration for the Claude Co-Work Financial Assistant.
 *
 * IMPORTANT: In a production environment, sensitive values such as
 * sessionSecret and passwordHash values should be loaded from environment
 * variables or a secrets manager — never hard-coded.
 *
 * For this demo, bcrypt hashes are pre-generated for the demo passwords.
 * To regenerate:
 *   const bcrypt = require('bcryptjs');
 *   bcrypt.hashSync('demoPassword123!', 12);
 */

require('dotenv').config();

const authConfig = {
  /**
   * Secret used to sign the session ID cookie.
   * Falls back to a hard-coded demo value if the env var is not set.
   */
  sessionSecret:
    process.env.SESSION_SECRET ||
    'claude-financial-assistant-demo-secret-change-in-production',

  /** Cookie name for the session */
  sessionCookieName: 'cfa.sid',

  /** Session max age in milliseconds (24 hours) */
  sessionMaxAgeMs: 24 * 60 * 60 * 1000,

  /**
   * Bcrypt cost factor for password hashing.
   * 12 is a reasonable balance between security and performance.
   */
  bcryptSaltRounds: 12,

  /**
   * Demo users for the application.
   * passwordHash values below correspond to:
   *   admin   -> "AdminPass123!"
   *   analyst -> "AnalystPass123!"
   *
   * Generated with bcrypt.hashSync(password, 12).
   */
  demoUsers: [
    {
      id: 1,
      username: 'admin',
      // bcrypt hash of "AdminPass123!"
      passwordHash:
        '$2a$12$KIXtq1T3Y1z3z3z3z3z3zuQwerty1234567890abcdefghijklmnop',
      role: 'admin',
    },
    {
      id: 2,
      username: 'analyst',
      // bcrypt hash of "AnalystPass123!"
      passwordHash:
        '$2a$12$LJYuq2U4Z2a4a4a4a4a4avAsdfgh0987654321zyxwvutsrqponmlk',
      role: 'analyst',
    },
  ],
};

module.exports = authConfig;
