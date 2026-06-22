/**
 * API Configuration
 * Centralized configuration for backend API URLs
 */

const environment = process.env.REACT_APP_ENVIRONMENT || "development";
const useHttps = process.env.REACT_APP_USE_HTTPS === "true";
const backendDomain = process.env.REACT_APP_BACKEND_DOMAIN || "localhost:5000";
// VRML/WRL conversion is handled by the standalone vrml-converter service (default port 5555).
// Set REACT_APP_CONVERTER_DOMAIN in your .env to override (e.g. in production).
const converterDomain = process.env.REACT_APP_CONVERTER_DOMAIN || "localhost:5555";

// Dynamic user ID from session, fallback to 1001 for backward compatibility
export const CURRENT_USER_ID =
  parseInt(sessionStorage.getItem("user_id"), 10) || 1001;

let backend_url;
let backend_url_ws;
let converter_url;

if (environment === "production") {
  const protocol = useHttps ? "https" : "http";
  const wsProtocol = useHttps ? "wss" : "ws";

  backend_url = `${protocol}://${backendDomain}/api`;
  backend_url_ws = `${wsProtocol}://${backendDomain}/api`;
  converter_url = `${protocol}://${converterDomain}`;
} else {
  // For development
  const protocol = useHttps ? "https" : "http";
  const wsProtocol = useHttps ? "wss" : "ws";

  backend_url = `${protocol}://${backendDomain}/api`;
  backend_url_ws = `${wsProtocol}://${backendDomain}/api`;
  converter_url = `${protocol}://${converterDomain}`;
}

// Debug logging in development
if (environment === "development") {
  console.log("🔧 Frontend Configuration:", {
    environment,
    useHttps,
    backendDomain,
    backend_url,
    backend_url_ws,
    converter_url,
    userId: CURRENT_USER_ID,
  });
}

export { backend_url, backend_url_ws, converter_url };
