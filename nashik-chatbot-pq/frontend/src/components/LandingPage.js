import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "./LandingPage.css";
import traceabilityIcon from "../assests/traceability.png";
import qualityIcon from "../assests/quality.png";
import guidelineIcon from "../assests/guideline.png";
import supportIcon from "../assests/support.png";
import dashboardIcon from "../assests/dashboard.png";
import utilityLogo from "../assests/image.png";
import mahindraRiseLogo from "../assests/mahindra_rise_logo.png";
import { authService } from "../services/api";

function LandingPage() {
  const navigate = useNavigate();

  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [justLoggedIn, setJustLoggedIn] = useState(false);
  const [isSignup, setIsSignup] = useState(false);
  const [username, setUsername] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setIsLoggedIn(authService.isLoggedIn());
  }, []);

  // Features visible per role
  const ROLE_FEATURES = {
    admin:        ["traceability", "guideline", "part-labeler", "part-labeler-plant", "z-stage"],
    user:         ["traceability", "guideline", "part-labeler", "part-labeler-plant", "z-stage"],
    part_labeler: ["part-labeler", "part-labeler-plant"],
  };

  const currentRole = authService.getUserRole();
  const enabledFeatures = ROLE_FEATURES[currentRole] || ROLE_FEATURES["user"];
  const features = [
    {
      id: "traceability",
      title: "Traceability",
      icon: traceabilityIcon,
      description: "Track and trace quality issues across the production chain",
      route: "/chat?feature=traceability",
    },
    {
      id: "guideline",
      title: "Qlense guideline and standard",
      icon: guidelineIcon,
      description: "Access quality guidelines and industry standards",
      route: "/chat?feature=guideline",
    },
  {
      id: "part-labeler",
      title: "Part Sense Visualizer Field",
      icon: dashboardIcon,
      description: "Interactive failure trend analysis",
      route: "/part-labeler",
    },
    {
      id: "part-labeler-plant",
      title: "Part Sense Visualizer Plant",
      icon: dashboardIcon,
      description: "Interactive failure trend analysis across all data sources",
      route: "/part-labeler?mode=plant",
    },
    {
      id: "z-stage",
      title: "Z-Stage Layout Preparation",
      icon: dashboardIcon,
      description: "Design and visualize production layouts with Z-Stage",
      route: "/z-stage",
    },
    {
      id: "quality-assistant",
      title: "Qlense Quality assistant",
      icon: qualityIcon,
      description: "AI-powered quality analysis and insights",
      route: "/chat?feature=quality-assistant",
    },
    {
      id: "diagnostic",
      title: "Diagnostic support system",
      icon: supportIcon,
      description: "Advanced diagnostic tools for quality control",
      route: "/chat?feature=diagnostic",
    },
  ];

  const handleGetStarted = (route) => {
    navigate(route);
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await authService.login(username, password);
      setJustLoggedIn(true);
      setIsLoggedIn(true);
      setUsername("");
      setPassword("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSignup = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await authService.signup(username, firstName, lastName, email, password);
      // After signup, auto-login
      await authService.login(username, password);
      setJustLoggedIn(true);
      setIsLoggedIn(true);
      setUsername("");
      setFirstName("");
      setLastName("");
      setPassword("");
      setEmail("");
      setIsSignup(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const toggleMode = () => {
    setIsSignup(!isSignup);
    setError("");
    setUsername("");
    setFirstName("");
    setLastName("");
    setPassword("");
    setEmail("");
  };

  return (
    <div className="landing-page">
      {/* Top Corner Logos */}
      <img
        src={utilityLogo}
        alt="Mahindra Utility Logo"
        className="corner-logo corner-logo-left"
      />
      <img
        src={mahindraRiseLogo}
        alt="Mahindra Rise Logo"
        className="corner-logo corner-logo-right"
      />

      <div className="landing-content">
        {/* Left Section - AI Solution Text */}
        <div className="left-section">
          <div className="ai-solution-text">
            <h1 className="main-heading">
              <span className="word word-1">AI-Powered</span>
              <span className="word word-2">Quality</span>
              <span className="word word-3">Management</span>
            </h1>
            <p className="sub-heading">
              Intelligent solutions for traceability, quality assurance, and
              diagnostic support
            </p>
          </div>
        </div>

        {/* Right Section - Auth Form or Features */}
        {!isLoggedIn ? (
          <div className="auth-container">
            <div className="auth-card">
              <h2 className="auth-title">
                {isSignup ? "Create Account" : "Welcome Back"}
              </h2>
              <p className="auth-subtitle">
                {isSignup
                  ? "Sign up to get started"
                  : "Login to access your dashboard"}
              </p>

              {error && <div className="auth-error">{error}</div>}

              <form onSubmit={isSignup ? handleSignup : handleLogin}>
                <div className="auth-field">
                  <label>Username</label>
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="Enter your username"
                    required
                  />
                </div>

                {isSignup && (
                  <div className="auth-name-row">
                    <div className="auth-field">
                      <label>First Name</label>
                      <input
                        type="text"
                        value={firstName}
                        onChange={(e) => setFirstName(e.target.value)}
                        placeholder="First name"
                        required
                      />
                    </div>
                    <div className="auth-field">
                      <label>Last Name</label>
                      <input
                        type="text"
                        value={lastName}
                        onChange={(e) => setLastName(e.target.value)}
                        placeholder="Last name"
                        required
                      />
                    </div>
                  </div>
                )}

                {isSignup && (
                  <div className="auth-field">
                    <label>Email</label>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="Enter your email"
                      required
                    />
                  </div>
                )}

                <div className="auth-field">
                  <label>Password</label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    required
                  />
                </div>

                <button
                  type="submit"
                  className="auth-submit-btn"
                  disabled={loading}
                >
                  {loading
                    ? "Please wait..."
                    : isSignup
                    ? "Sign Up"
                    : "Login"}
                </button>
              </form>

              <div className="auth-toggle">
                {isSignup ? (
                  <span>
                    Already have an account?{" "}
                    <button className="auth-toggle-btn" onClick={toggleMode}>
                      Login
                    </button>
                  </span>
                ) : (
                  <span>
                    Don't have an account?{" "}
                    <button className="auth-toggle-btn" onClick={toggleMode}>
                      Sign Up
                    </button>
                  </span>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className={`features-wrapper ${justLoggedIn ? "features-enter" : ""}`}>
            {/* Top bar: greeting + logout */}
            <div className="features-topbar">
              <span className="features-greeting">
                Welcome, <strong>{authService.getFullName()}</strong>
                <span className="features-role-badge">{currentRole}</span>
              </span>
              <button
                className="logout-btn"
                onClick={async () => {
                  await authService.logout();
                  setIsLoggedIn(false);
                  setJustLoggedIn(false);
                }}
              >
                Logout
              </button>
            </div>

            <div className={`features-container ${justLoggedIn ? "features-enter" : ""}`}>
              {/* Regular feature cards — filtered by role */}
              {features
                .filter((f) => enabledFeatures.includes(f.id))
                .map((feature, index) => (
                  <div
                    key={feature.id}
                    className={`feature-card ${justLoggedIn ? "feature-card-enter" : ""}`}
                    style={justLoggedIn ? { animationDelay: `${index * 0.12}s`, cursor: "pointer" } : { cursor: "pointer" }}
                    onClick={() => handleGetStarted(feature.route)}
                  >
                    <div className="feature-content">
                      <img src={feature.icon} alt={feature.title} className="feature-icon" />
                      <div className="feature-info">
                        <h3 className="feature-title">{feature.title}</h3>
                        <p className="feature-description">{feature.description}</p>
                      </div>
                    </div>
                    <button
                      className="get-started-btn"
                      onClick={(e) => { e.stopPropagation(); handleGetStarted(feature.route); }}
                    >
                      Get started
                      <span className="arrow-icon">&rarr;</span>
                    </button>
                  </div>
                ))}

              {/* Admin Panel card — only for admin role */}
              {currentRole === "admin" && (
                <div
                  className={`feature-card feature-card-admin ${justLoggedIn ? "feature-card-enter" : ""}`}
                  style={{ cursor: "pointer" }}
                  onClick={() => handleGetStarted("/admin")}
                >
                  <div className="feature-content">
                    <img src={dashboardIcon} alt="Admin Panel" className="feature-icon" />
                    <div className="feature-info">
                      <h3 className="feature-title">Admin Panel</h3>
                      <p className="feature-description">
                        Manage users, assign roles, and control access
                      </p>
                    </div>
                  </div>
                  <button
                    className="get-started-btn"
                    onClick={(e) => { e.stopPropagation(); handleGetStarted("/admin"); }}
                  >
                    Open
                    <span className="arrow-icon">&rarr;</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default LandingPage;
