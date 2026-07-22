import React, { Suspense, lazy } from "react";
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from "react-router-dom";
import "./App.css";
import LandingPage from "./components/LandingPage";
import LoadingAnimation from "./components/LoadingAnimation";
import authService from "./services/api/authService";

// Code-split the heavier pages (ZStage pulls in three.js + loaders, ChatPage
// pulls in react-pdf/recharts) so their JS only loads when actually visited,
// instead of bloating the initial bundle every user pays for on first load.
const ChatPage = lazy(() => import("./components/ChatPage"));
const PartLabeler = lazy(() => import("./components/PartLabeler/PartLabeler"));
const ZStage = lazy(() => import("./components/ZStage/ZStage"));
const AdminPanel = lazy(() => import("./components/AdminPanel/AdminPanel"));

/**
 * ProtectedRoute
 * - Redirects to "/" if not logged in.
 * - Redirects to "/" if user's role doesn't allow the current path.
 */
function ProtectedRoute({ children }) {
  const location = useLocation();

  if (!authService.isLoggedIn()) {
    return <Navigate to="/" replace />;
  }

  if (!authService.canAccess(location.pathname + location.search)) {
    return <Navigate to="/" replace />;
  }

  return children;
}

/**
 * AdminRoute — only accessible by admin role.
 */
function AdminRoute({ children }) {
  if (!authService.isLoggedIn()) {
    return <Navigate to="/" replace />;
  }
  if (!authService.isAdmin()) {
    return <Navigate to="/" replace />;
  }
  return children;
}

function App() {
  return (
    <Router>
      <Suspense fallback={<LoadingAnimation message="Loading..." />}>
      <Routes>
        <Route path="/" element={<LandingPage />} />

        <Route
          path="/chat"
          element={
            <ProtectedRoute>
              <ChatPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/part-labeler"
          element={
            <ProtectedRoute>
              <PartLabeler />
            </ProtectedRoute>
          }
        />

        <Route
          path="/z-stage"
          element={
            <ProtectedRoute>
              <ZStage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/admin"
          element={
            <AdminRoute>
              <AdminPanel />
            </AdminRoute>
          }
        />
      </Routes>
      </Suspense>
    </Router>
  );
}

export default App;
