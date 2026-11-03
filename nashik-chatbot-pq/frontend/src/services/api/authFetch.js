/**
 * Attaches the bearer token to every request made to our backend and signs the
 * user out on 401. Imported once from index.js (before the app renders).
 */
import axios from "axios";
import { backend_url } from "./config";
import authService from "./authService";

function handleUnauthorized(url) {
  // A wrong password on /auth/login is also a 401: don't bounce the login form.
  if (String(url).includes("/auth/")) return;
  // No token and not logged in: nothing to clear. Otherwise (e.g. a session
  // that started before tokens existed) send the user back to log in.
  if (!authService.getToken() && !authService.isLoggedIn()) return;
  authService.logout();
  window.location.assign("/");
}

export function attachAuth(instance) {
  instance.interceptors.request.use((config) => {
    const token = authService.getToken();
    if (token) {
      config.headers = config.headers || {};
      if (!config.headers.Authorization) config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });
  instance.interceptors.response.use(
    (r) => r,
    (err) => {
      if (err?.response?.status === 401) handleUnauthorized(err.config?.url || "");
      return Promise.reject(err);
    }
  );
}

attachAuth(axios);

const origFetch = window.fetch.bind(window);
window.fetch = async (input, init = {}) => {
  const url = typeof input === "string" ? input : input?.url || "";
  if (!url.startsWith(backend_url)) return origFetch(input, init);
  const token = authService.getToken();
  const headers = new Headers(init.headers || (typeof input !== "string" ? input.headers : undefined));
  if (token && !headers.has("Authorization")) headers.set("Authorization", `Bearer ${token}`);
  const res = await origFetch(input, { ...init, headers });
  if (res.status === 401) handleUnauthorized(url);
  return res;
};
