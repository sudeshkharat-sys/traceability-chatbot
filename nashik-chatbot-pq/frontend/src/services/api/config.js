/**
 * API Configuration
 * Centralized configuration for backend API URLs
 */

const environment = process.env.REACT_APP_ENVIRONMENT || "development";
const useHttps = process.env.REACT_APP_USE_HTTPS === "true";
const backendDomain = process.env.REACT_APP_BACKEND_DOMAIN || "localhost:5000";

// Dynamic user ID from session, fallback to 1001 for backward compatibility
export const CURRENT_USER_ID =
  parseInt(sessionStorage.getItem("user_id"), 10) || 1001;

let backend_url;
let backend_url_ws;

if (environment === "production") {
  const protocol = useHttps ? "https" : "http";
  const wsProtocol = useHttps ? "wss" : "ws";

  backend_url = `${protocol}://${backendDomain}/api`;
  backend_url_ws = `${wsProtocol}://${backendDomain}/api`;
} else {
  // For development
  const protocol = useHttps ? "https" : "http";
  const wsProtocol = useHttps ? "wss" : "ws";

  backend_url = `${protocol}://${backendDomain}/api`;
  backend_url_ws = `${wsProtocol}://${backendDomain}/api`;
}

// Debug logging in development
if (environment === "development") {
  console.log("🔧 Frontend Configuration:", {
    environment,
    useHttps,
    backendDomain,
    backend_url,
    backend_url_ws,
    userId: CURRENT_USER_ID,
  });
}

export { backend_url, backend_url_ws };

