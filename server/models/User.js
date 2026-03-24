'use strict';

const bcrypt = require('bcryptjs');
const authConfig = require('../../config/authConfig');

/**
 * User model representing a demo user in the system.
 * Provides static methods for user lookup and password management.
 *
 * In a production system this would interface with a real database.
 * For the demo, it operates against the in-memory demoUsers list
 * defined in authConfig.
 */
class User {
  /**
   * @param {object} data
   * @param {number} data.id
   * @param {string} data.username
   * @param {string} data.passwordHash - bcrypt hash of the user's password
   * @param {string} data.role
   */
  constructor({ id, username, passwordHash, role }) {
    this.id = id;
    this.username = username;
    this.passwordHash = passwordHash;
    this.role = role;
  }

  /**
   * Returns a plain object representation of the user,
   * excluding the password hash for safe serialization.
   *
   * @returns {{ id: number, username: string, role: string }}
   */
  toSafeObject() {
    return {
      id: this.id,
      username: this.username,
      role: this.role,
    };
  }

  /**
   * Verifies a plain-text password against this user's stored hash.
   *
   * @param {string} plainPassword - The plain-text password to verify.
   * @returns {Promise<boolean>} True if the password matches, false otherwise.
   */
  async verifyPassword(plainPassword) {
    if (!plainPassword) return false;
    return bcrypt.compare(plainPassword, this.passwordHash);
  }

  // ---------------------------------------------------------------------------
  // Static factory / query methods
  // ---------------------------------------------------------------------------

  /**
   * Finds a user by username from the demo users list.
   *
   * @param {string} username
   * @returns {User|null} A User instance or null if not found.
   */
  static findByUsername(username) {
    if (!username) return null;
    const data = authConfig.demoUsers.find((u) => u.username === username);
    return data ? new User(data) : null;
  }

  /**
   * Finds a user by their numeric ID from the demo users list.
   *
   * @param {number} id
   * @returns {User|null} A User instance or null if not found.
   */
  static findById(id) {
    if (id === undefined || id === null) return null;
    const data = authConfig.demoUsers.find((u) => u.id === id);
    return data ? new User(data) : null;
  }

  /**
   * Returns all demo users as User instances (without password hashes
   * exposed in the returned safe objects).
   *
   * @returns {User[]}
   */
  static findAll() {
    return authConfig.demoUsers.map((data) => new User(data));
  }

  /**
   * Hashes a plain-text password using bcrypt.
   * Useful for generating new demo user hashes.
   *
   * @param {string} plainPassword
   * @returns {Promise<string>} The bcrypt hash.
   */
  static async hashPassword(plainPassword) {
    if (!plainPassword) {
      throw new Error('Password must not be empty.');
    }
    return bcrypt.hash(plainPassword, authConfig.bcryptSaltRounds);
  }
}

module.exports = User;
