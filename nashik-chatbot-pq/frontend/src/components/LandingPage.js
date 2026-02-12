import React from "react";
import { useNavigate } from "react-router-dom";
import "./LandingPage.css";
import traceabilityIcon from "../assests/traceability.png";
import qualityIcon from "../assests/quality.png";
import guidelineIcon from "../assests/guideline.png";
import supportIcon from "../assests/support.png";
import utilityLogo from "../assests/Mahindra_Logo_utilty.png";
import mahindraRiseLogo from "../assests/mahindra_rise_logo.png";

function LandingPage() {
  const navigate = useNavigate();

  const enabledFeatures = ["traceability", "guideline"];

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
              Intelligent solutions for traceability, quality assurance, and diagnostic support
            </p>
          </div>
        </div>

        {/* Right Section - Features List */}
        <div className="features-container">
          {features.map((feature) => {
            const isEnabled = enabledFeatures.includes(feature.id);
            return (
              <div
                key={feature.id}
                className="feature-card"
                onClick={() => isEnabled && handleGetStarted(feature.route)}
                style={
                  !isEnabled
                    ? { cursor: "not-allowed", opacity: 0.6 }
                    : { cursor: "pointer" }
                }
              >
                <div className="feature-content">
                  <img
                    src={feature.icon}
                    alt={feature.title}
                    className="feature-icon"
                  />
                  <div className="feature-info">
                    <h3 className="feature-title">{feature.title}</h3>
                    <p className="feature-description">{feature.description}</p>
                  </div>
                </div>
                <button
                  className="get-started-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (isEnabled) {
                      handleGetStarted(feature.route);
                    }
                  }}
                  disabled={!isEnabled}
                  style={!isEnabled ? { cursor: "not-allowed" } : {}}
                >
                  Get started
                  <span className="arrow-icon">→</span>
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default LandingPage;
