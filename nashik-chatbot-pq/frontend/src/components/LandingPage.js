import React from "react";
import { useNavigate } from "react-router-dom";
import "./LandingPage.css";
import traceabilityIcon from "../assests/traceability.png";
import qualityIcon from "../assests/quality.png";
import guidelineIcon from "../assests/guideline.png";
import supportIcon from "../assests/support.png";

function LandingPage() {
  const navigate = useNavigate();

  const features = [
    {
      id: "traceability",
      title: "Traceability",
      icon: traceabilityIcon,
      description: "Track and trace quality issues across the production chain",
      route: "/chat?feature=traceability",
    },
    {
      id: "quality-assistant",
      title: "Qlense Quality assistant",
      icon: qualityIcon,
      description: "AI-powered quality analysis and insights",
      route: "/chat?feature=quality-assistant",
    },
    {
      id: "guideline",
      title: "Qlense guideline and standard",
      icon: guidelineIcon,
      description: "Access quality guidelines and industry standards",
      route: "/chat?feature=guideline",
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
      <div className="landing-content">
        {/* Image Section - Left Side */}
        <div className="image-section">
          <img
            src={traceabilityIcon}
            alt="Traceability System"
            className="landing-image"
          />
        </div>

        {/* Features List - Right Side */}
        <div className="features-container">
          {features.map((feature) => (
            <div
              key={feature.id}
              className="feature-card"
              onClick={() => handleGetStarted(feature.route)}
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
                  handleGetStarted(feature.route);
                }}
              >
                Get started
                <span className="arrow-icon">→</span>
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default LandingPage;
