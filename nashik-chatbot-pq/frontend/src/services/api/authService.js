/**
 * Authentication Service
 * Handles signup, login, logout and session management
 */

import { backend_url } from "./config";

// Single source of truth for which modules each role may open.
// New signups get "user" (minimal); an admin then assigns the real role.
export const ROLE_ALLOWED = {
  user:               ["part-labeler", "guideline"],
  pfmea_advisor:      ["pfmea", "part-labeler-plant"],
  part_labeler:       ["part-labeler", "part-labeler-plant", "guideline"],
  part_labeler_field: ["part-labeler", "guideline"],
  part_labeler_plant: ["part-labeler-plant", "z-stage", "guideline", "pfmea"],
  part_labeler_ev:    ["part-labeler-ev", "z-stage", "guideline"],
};

// Map a route (path + query) to a module id from the landing page.
function moduleIdForPath(path) {
  const [pathname, query = ""] = path.split("?");
  const params = new URLSearchParams(query);
  if (pathname.startsWith("/part-labeler")) {
    const mode = params.get("mode");
    if (mode === "plant") return "part-labeler-plant";
    if (mode === "ev") return "part-labeler-ev";
    return "part-labeler";
  }
  if (pathname.startsWith("/z-stage")) return "z-stage";
  if (pathname.startsWith("/pfmea")) return "pfmea";
  if (pathname.startsWith("/chat")) return params.get("feature");
  return null;
}

class AuthService {
  /**
   * Sign up a new user
   * @param {string} username
   * @param {string} firstName
   * @param {string} lastName
   * @param {string} email
   * @param {string} password
   * @returns {Promise<{user_id: number, username: string, first_name: string, last_name: string, message: string}>}
   */
  async signup(username, firstName, lastName, email, password) {
    const response = await fetch(`${backend_url}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username,
        first_name: firstName,
        last_name: lastName,
        email,
        password,
      }),
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
    sessionStorage.setItem("token", data.token || "");
    sessionStorage.setItem("user_id", data.user_id);
    sessionStorage.setItem("username", data.username);
    sessionStorage.setItem("first_name", data.first_name || "");
    sessionStorage.setItem("last_name", data.last_name || "");
    sessionStorage.setItem("role", data.role || "user");
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
    sessionStorage.removeItem("first_name");
    sessionStorage.removeItem("last_name");
    sessionStorage.removeItem("role");
    sessionStorage.removeItem("token");
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

  /**
   * Get user's full name from session
   * @returns {string}
   */
  getFullName() {
    const first = sessionStorage.getItem("first_name") || "";
    const last = sessionStorage.getItem("last_name") || "";
    const full = `${first} ${last}`.trim();
    return full || this.getUsername() || "User";
  }

  /**
   * Get current user role from session
   * @returns {"admin"|"user"|"part_labeler"}
   */
  getUserRole() {
    return sessionStorage.getItem("role") || "user";
  }

  /**
   * Check if current user is an admin
   * @returns {boolean}
   */
  isAdmin() {
    return this.getUserRole() === "admin";
  }

  /**
   * Check if current user has access to a given route
   * part_labeler → only /part-labeler
   * user / admin  → all routes
   * @param {string} path
   * @returns {boolean}
   */
  async resetPassword(username, currentPassword, newPassword) {
    const response = await fetch(`${backend_url}/auth/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, current_password: currentPassword, new_password: newPassword }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Password reset failed");
    }
    return response.json();
  }

  getToken() {
    return sessionStorage.getItem("token") || "";
  }

  /**
   * Append the access token to a URL that the browser (not fetch/axios) will
   * request, e.g. file downloads and 3D-model loaders, which cannot send headers.
   */
  withToken(url) {
    const t = this.getToken();
    if (!t) return url;
    return url + (url.includes("?") ? "&" : "?") + "access_token=" + encodeURIComponent(t);
  }

  canAccess(path) {
    const role = this.getUserRole();
    if (role === "admin") return true;
    const allowed = ROLE_ALLOWED[role];
    if (!allowed) return false;
    const id = moduleIdForPath(path);
    return id !== null && allowed.includes(id);
  }
}

const authService = new AuthService();
export default authService;
