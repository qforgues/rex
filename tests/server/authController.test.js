'use strict';

/**
 * Tests for authentication middleware and routes.
 *
 * These tests use Jest + Supertest to verify:
 *  - The authenticateUser middleware correctly validates Basic Auth credentials.
 *  - The /login route creates a session on valid credentials.
 *  - The /logout route destroys the session.
 *  - The /me route reflects session state.
 *  - The User model behaves correctly.
 */

const request = require('supertest');
const express = require('express');
const bcrypt = require('bcryptjs');

// ---- Mocks ----------------------------------------------------------------

// We mock authConfig so tests are not dependent on real bcrypt hashes
jest.mock('../../config/authConfig', () => ({
  sessionSecret: 'test-secret',
  sessionCookieName: 'cfa.sid',
  sessionMaxAgeMs: 86400000,
  bcryptSaltRounds: 10,
  demoUsers: [
    {
      id: 1,
      username: 'admin',
      // bcrypt hash of "AdminPass123!" generated with saltRounds=10
      passwordHash: '', // filled in beforeAll
      role: 'admin',
    },
  ],
}));

// ---- Setup ----------------------------------------------------------------

const authConfig = require('../../config/authConfig');
const { authenticateUser } = require('../../server/middleware/authMiddleware');
const authRoutes = require('../../server/routes/authRoutes');
const User = require('../../server/models/User');

/**
 * Build a minimal Express app for testing.
 * We use a simple in-memory session store to avoid SQLite dependency in tests.
 */
function buildTestApp() {
  const app = express();
  app.use(express.json());

  // Minimal in-memory session middleware for testing
  const session = require('express-session');
  app.use(
    session({
      secret: authConfig.sessionSecret,
      resave: false,
      saveUninitialized: false,
      name: authConfig.sessionCookieName,
    })
  );

  // Mount auth routes
  app.use('/auth', authRoutes);

  // A protected route to test the middleware
  app.get('/protected', authenticateUser, (req, res) => {
    res.status(200).json({ message: 'Access granted', user: req.user });
  });

  return app;
}

// ---- Lifecycle ------------------------------------------------------------

beforeAll(async () => {
  // Generate a real bcrypt hash for the demo user so password comparison works
  const hash = await bcrypt.hash('AdminPass123!', 10);
  authConfig.demoUsers[0].passwordHash = hash;
});

// ---- Tests ----------------------------------------------------------------

describe('User model', () => {
  test('findByUsername returns a User for a known username', () => {
    const user = User.findByUsername('admin');
    expect(user).not.toBeNull();
    expect(user.username).toBe('admin');
    expect(user.role).toBe('admin');
  });

  test('findByUsername returns null for an unknown username', () => {
    const user = User.findByUsername('unknown');
    expect(user).toBeNull();
  });

  test('findById returns a User for a known id', () => {
    const user = User.findById(1);
    expect(user).not.toBeNull();
    expect(user.id).toBe(1);
  });

  test('findById returns null for an unknown id', () => {
    const user = User.findById(999);
    expect(user).toBeNull();
  });

  test('toSafeObject does not expose passwordHash', () => {
    const user = User.findByUsername('admin');
    const safe = user.toSafeObject();
    expect(safe).not.toHaveProperty('passwordHash');
    expect(safe).toHaveProperty('id');
    expect(safe).toHaveProperty('username');
    expect(safe).toHaveProperty('role');
  });

  test('verifyPassword returns true for correct password', async () => {
    const user = User.findByUsername('admin');
    const result = await user.verifyPassword('AdminPass123!');
    expect(result).toBe(true);
  });

  test('verifyPassword returns false for incorrect password', async () => {
    const user = User.findByUsername('admin');
    const result = await user.verifyPassword('WrongPassword!');
    expect(result).toBe(false);
  });

  test('hashPassword returns a bcrypt hash', async () => {
    const hash = await User.hashPassword('SomePassword!');
    expect(hash).toMatch(/^\$2[ab]\$/);
  });

  test('hashPassword throws for empty password', async () => {
    await expect(User.hashPassword('')).rejects.toThrow('Password must not be empty.');
  });
});

describe('authenticateUser middleware', () => {
  let app;

  beforeEach(() => {
    app = buildTestApp();
  });

  test('returns 401 when no Authorization header is provided', async () => {
    const res = await request(app).get('/protected');
    expect(res.status).toBe(401);
    expect(res.body).toHaveProperty('error', 'Authentication required');
  });

  test('returns 401 for invalid credentials', async () => {
    const credentials = Buffer.from('admin:WrongPassword!').toString('base64');
    const res = await request(app)
      .get('/protected')
      .set('Authorization', `Basic ${credentials}`);
    expect(res.status).toBe(401);
    expect(res.body).toHaveProperty('error', 'Invalid credentials');
  });

  test('returns 401 for unknown username', async () => {
    const credentials = Buffer.from('nobody:AdminPass123!').toString('base64');
    const res = await request(app)
      .get('/protected')
      .set('Authorization', `Basic ${credentials}`);
    expect(res.status).toBe(401);
  });

  test('grants access with valid credentials', async () => {
    const credentials = Buffer.from('admin:AdminPass123!').toString('base64');
    const res = await request(app)
      .get('/protected')
      .set('Authorization', `Basic ${credentials}`);
    expect(res.status).toBe(200);
    expect(res.body).toHaveProperty('message', 'Access granted');
    expect(res.body.user).toHaveProperty('username', 'admin');
    expect(res.body.user).not.toHaveProperty('passwordHash');
  });
});

describe('POST /auth/login', () => {
  let app;

  beforeEach(() => {
    app = buildTestApp();
  });

  test('returns 400 when username or password is missing', async () => {
    const res = await request(app)
      .post('/auth/login')
      .send({ username: 'admin' });
    expect(res.status).toBe(400);
    expect(res.body).toHaveProperty('error', 'Bad request');
  });

  test('returns 401 for invalid credentials', async () => {
    const res = await request(app)
      .post('/auth/login')
      .send({ username: 'admin', password: 'WrongPassword!' });
    expect(res.status).toBe(401);
    expect(res.body).toHaveProperty('error', 'Invalid credentials');
  });

  test('returns 200 and user info for valid credentials', async () => {
    const res = await request(app)
      .post('/auth/login')
      .send({ username: 'admin', password: 'AdminPass123!' });
    expect(res.status).toBe(200);
    expect(res.body).toHaveProperty('message', 'Login successful.');
    expect(res.body.user).toHaveProperty('username', 'admin');
    expect(res.body.user).not.toHaveProperty('passwordHash');
  });

  test('sets a session cookie on successful login', async () => {
    const res = await request(app)
      .post('/auth/login')
      .send({ username: 'admin', password: 'AdminPass123!' });
    expect(res.status).toBe(200);
    const cookies = res.headers['set-cookie'];
    expect(cookies).toBeDefined();
    expect(cookies.some((c) => c.startsWith('cfa.sid'))).toBe(true);
  });
});

describe('POST /auth/logout', () => {
  let app;

  beforeEach(() => {
    app = buildTestApp();
  });

  test('returns 200 even when no session exists', async () => {
    const res = await request(app).post('/auth/logout');
    expect(res.status).toBe(200);
  });

  test('destroys session after login then logout', async () => {
    const agent = request.agent(app);

    // Login to establish a session
    await agent
      .post('/auth/login')
      .send({ username: 'admin', password: 'AdminPass123!' })
      .expect(200);

    // Verify session is active
    const meRes = await agent.get('/auth/me');
    expect(meRes.status).toBe(200);
    expect(meRes.body.user).toHaveProperty('username', 'admin');

    // Logout
    const logoutRes = await agent.post('/auth/logout');
    expect(logoutRes.status).toBe(200);
    expect(logoutRes.body).toHaveProperty('message', 'Logout successful.');

    // Session should be gone
    const afterLogout = await agent.get('/auth/me');
    expect(afterLogout.status).toBe(401);
  });
});

describe('GET /auth/me', () => {
  let app;

  beforeEach(() => {
    app = buildTestApp();
  });

  test('returns 401 when not authenticated', async () => {
    const res = await request(app).get('/auth/me');
    expect(res.status).toBe(401);
  });

  test('returns user info when authenticated', async () => {
    const agent = request.agent(app);

    await agent
      .post('/auth/login')
      .send({ username: 'admin', password: 'AdminPass123!' })
      .expect(200);

    const res = await agent.get('/auth/me');
    expect(res.status).toBe(200);
    expect(res.body.user).toHaveProperty('username', 'admin');
    expect(res.body.user).toHaveProperty('role', 'admin');
  });
});
