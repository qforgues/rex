'use strict';

const express = require('express');
const bcrypt = require('bcryptjs');
const authConfig = require('../../config/authConfig');

const router = express.Router();

/**
 * POST /login
 * Authenticates a user with username and password from the request body.
 * On success, creates a session and returns user info.
 * On failure, returns a 401 response.
 */
router.post('/login', async (req, res) => {
  try {
    const { username, password } = req.body;

    // Validate that both fields are present
    if (!username || !password) {
      return res.status(400).json({
        error: 'Bad request',
        message: 'Both username and password are required.',
      });
    }

    // Find the user in the demo users list
    const demoUser = authConfig.demoUsers.find(
      (u) => u.username === username
    );

    if (!demoUser) {
      // Use a generic message to avoid username enumeration
      return res.status(401).json({
        error: 'Invalid credentials',
        message: 'Username or password is incorrect.',
      });
    }

    // Verify the password against the stored hash
    const passwordMatch = await bcrypt.compare(password, demoUser.passwordHash);

    if (!passwordMatch) {
      return res.status(401).json({
        error: 'Invalid credentials',
        message: 'Username or password is incorrect.',
      });
    }

    // Regenerate the session to prevent session fixation attacks
    req.session.regenerate((err) => {
      if (err) {
        console.error('[authRoutes] Session regeneration error:', err);
        return res.status(500).json({
          error: 'Internal server error',
          message: 'Failed to establish session.',
        });
      }

      // Store sanitized user info in the session
      req.session.user = {
        id: demoUser.id,
        username: demoUser.username,
        role: demoUser.role,
      };

      // Save the session before responding
      req.session.save((saveErr) => {
        if (saveErr) {
          console.error('[authRoutes] Session save error:', saveErr);
          return res.status(500).json({
            error: 'Internal server error',
            message: 'Failed to save session.',
          });
        }

        return res.status(200).json({
          message: 'Login successful.',
          user: {
            id: demoUser.id,
            username: demoUser.username,
            role: demoUser.role,
          },
        });
      });
    });
  } catch (err) {
    console.error('[authRoutes] Unexpected error during login:', err);
    return res.status(500).json({
      error: 'Internal server error',
      message: 'An unexpected error occurred.',
    });
  }
});

/**
 * POST /logout
 * Destroys the current user session.
 * Returns 200 on success, 500 if session destruction fails.
 */
router.post('/logout', (req, res) => {
  if (!req.session || !req.session.user) {
    // No active session — treat as already logged out
    return res.status(200).json({ message: 'No active session. Already logged out.' });
  }

  const username = req.session.user.username;

  req.session.destroy((err) => {
    if (err) {
      console.error('[authRoutes] Session destruction error:', err);
      return res.status(500).json({
        error: 'Internal server error',
        message: 'Failed to destroy session.',
      });
    }

    // Clear the session cookie from the client
    res.clearCookie(authConfig.sessionCookieName);

    console.log(`[authRoutes] User "${username}" logged out successfully.`);
    return res.status(200).json({ message: 'Logout successful.' });
  });
});

/**
 * GET /me
 * Returns the currently authenticated user's info from the session.
 * Useful for the UI to check authentication state.
 */
router.get('/me', (req, res) => {
  if (req.session && req.session.user) {
    return res.status(200).json({ user: req.session.user });
  }
  return res.status(401).json({
    error: 'Not authenticated',
    message: 'No active session found.',
  });
});

module.exports = router;
