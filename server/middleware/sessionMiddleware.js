'use strict';

const session = require('express-session');
const SQLiteStore = require('connect-sqlite3')(session);
const path = require('path');
const authConfig = require('../../config/authConfig');

/**
 * Configures and attaches session middleware to the Express application.
 * Uses SQLite as the session store for persistence across server restarts.
 *
 * @param {import('express').Application} app - The Express application instance.
 */
function initializeSession(app) {
  // Resolve the path for the SQLite session database
  const dbDir = path.resolve(__dirname, '../../data');

  const sessionStore = new SQLiteStore({
    db: 'sessions.db',
    dir: dbDir,
    table: 'sessions',
    // Clean up expired sessions every 24 hours (in seconds)
    cleanupInterval: 24 * 60 * 60,
  });

  sessionStore.on('error', (err) => {
    console.error('[sessionMiddleware] SQLite session store error:', err);
  });

  app.use(
    session({
      secret: authConfig.sessionSecret,
      store: sessionStore,
      resave: false,
      saveUninitialized: false,
      name: authConfig.sessionCookieName,
      cookie: {
        // Milliseconds: default 24 hours
        maxAge: authConfig.sessionMaxAgeMs,
        httpOnly: true,
        // Set to true in production with HTTPS
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
      },
    })
  );

  console.log('[sessionMiddleware] Session middleware initialized with SQLite store.');
}

module.exports = { initializeSession };
