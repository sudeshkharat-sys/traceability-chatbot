/**
 * Authentication Service
 * Handles signup, login, logout and session management
 */

import { backend_url } from "./config";

class AuthService {
  /**
   * Sign up a new user
   * @param {string} username
   * @param {string} email
   * @param {string} password
   * @returns {Promise<{user_id: number, username: string, message: string}>}
   */
  async signup(username, email, password) {
    const response = await fetch(`${backend_url}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, email, password }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Signup failed");
    }

    const data = await response.json();
    return data;
  }

  /**
   * Log in an existing user
   * @param {string} username
   * @param {string} password
   * @returns {Promise<{user_id: number, username: string, message: string}>}
   */
  async login(username, password) {
    const response = await fetch(`${backend_url}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Login failed");
    }

    const data = await response.json();

    // Save session to sessionStorage
    sessionStorage.setItem("user_id", data.user_id);
    sessionStorage.setItem("username", data.username);
    sessionStorage.setItem("isLoggedIn", "true");

    return data;
  }

  /**
   * Log out the current user and clear session
   */
  async logout() {
    try {
      await fetch(`${backend_url}/auth/logout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
    } catch (e) {
      console.error("Logout API call failed:", e);
    }

    // Always clear session regardless of API result
    sessionStorage.removeItem("user_id");
    sessionStorage.removeItem("username");
    sessionStorage.removeItem("isLoggedIn");
  }

  /**
   * Check if user is currently logged in
   * @returns {boolean}
   */
  isLoggedIn() {
    return sessionStorage.getItem("isLoggedIn") === "true";
  }

  /**
   * Get current user ID from session
   * @returns {number|null}
   */
  getUserId() {
    const id = sessionStorage.getItem("user_id");
    return id ? parseInt(id, 10) : null;
  }

  /**
   * Get current username from session
   * @returns {string|null}
   */
  getUsername() {
    return sessionStorage.getItem("username");
  }
}

const authService = new AuthService();
export default authService;
