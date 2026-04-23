import React from "react";
import "./LoadingAnimation.css";

const LoadingAnimation = ({ message = "Thinking..." }) => {
  return (
    <div className="loading-animation-container">
      <div className="dots-and-text">
        <div className="dots-loader">
          <div className="dot dot-1"></div>
          <div className="dot dot-2"></div>
          <div className="dot dot-3"></div>
        </div>
        <span className="loading-text-animated">{message}</span>
      </div>
    </div>
  );
};

export default LoadingAnimation;
