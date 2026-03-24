'use strict';

const bcrypt = require('bcryptjs');
const authConfig = require('../../config/authConfig');

/**
 * Middleware to authenticate users using Basic Authentication.
 * Checks the Authorization header for credentials and verifies them
 * against the configured demo users.
 *
 * @param {import('express').Request} req
 * @param {import('express').Response} res
 * @param {import('express').NextFunction} next
 */
async function authenticateUser(req, res, next) {
  try {
    // Allow already-authenticated sessions to pass through
    if (req.session && req.session.user) {
      return next();
    }

    const authHeader = req.headers['authorization'];

    if (!authHeader || !authHeader.startsWith('Basic ')) {
      res.set('WWW-Authenticate', 'Basic realm="Claude Financial Assistant"');
      return res.status(401).json({
        error: 'Authentication required',
        message: 'Please provide valid Basic Authentication credentials.',
      });
    }

    // Decode Base64-encoded "username:password"
    const base64Credentials = authHeader.slice('Basic '.length);
    const decoded = Buffer.from(base64Credentials, 'base64').toString('utf8');
    const colonIndex = decoded.indexOf(':');

    if (colonIndex === -1) {
      return res.status(401).json({
        error: 'Invalid credentials format',
        message: 'Authorization header must be in the format: Basic base64(username:password)',
      });
    }

    const username = decoded.substring(0, colonIndex);
    const password = decoded.substring(colonIndex + 1);

    if (!username || !password) {
      return res.status(401).json({
        error: 'Invalid credentials',
        message: 'Username and password are required.',
      });
    }

    // Look up the user in the demo users list
    const demoUser = authConfig.demoUsers.find(
      (u) => u.username === username
    );

    if (!demoUser) {
      return res.status(401).json({
        error: 'Invalid credentials',
        message: 'Username or password is incorrect.',
      });
    }

    // Compare the provided password against the stored hash
    const passwordMatch = await bcrypt.compare(password, demoUser.passwordHash);

    if (!passwordMatch) {
      return res.status(401).json({
        error: 'Invalid credentials',
        message: 'Username or password is incorrect.',
      });
    }

    // Attach sanitized user info to the request object
    req.user = {
      id: demoUser.id,
      username: demoUser.username,
      role: demoUser.role,
    };

    return next();
  } catch (err) {
    console.error('[authMiddleware] Unexpected error during authentication:', err);
    return res.status(500).json({
      error: 'Internal server error',
      message: 'An unexpected error occurred during authentication.',
    });
  }
}

module.exports = { authenticateUser };
