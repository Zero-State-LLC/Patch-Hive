/**
 * PatchHive Loading Spinner
 * Rotating hexagon with signal flow — token color, no glow blur.
 */
import React from "react";
import "./LoadingSpinner.css";

interface LoadingSpinnerProps {
  size?: number;
  message?: string;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({ size = 80, message }) => {
  return (
    <div className="loading-spinner-container" role="status" aria-live="polite">
      <svg
        role="img"
        aria-label={message || "Loading"}
        width={size}
        height={size}
        viewBox="0 0 100 100"
        xmlns="http://www.w3.org/2000/svg"
        className="loading-spinner"
      >
        <polygon
          points="50,10 80,25 80,60 50,75 20,60 20,25"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          className="spinner-hex"
        />
        <polygon
          points="50,20 70,30 70,55 50,65 30,55 30,30"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          opacity="0.6"
          className="spinner-hex-inner"
        />
        <circle
          cx="50"
          cy="42.5"
          r="8"
          fill="currentColor"
          opacity="0.4"
          className="spinner-core"
        />
        <circle cx="50" cy="42.5" r="4" fill="currentColor" className="spinner-core-inner" />
        <circle cx="50" cy="10" r="2.5" fill="currentColor" className="spinner-dot dot-1" />
        <circle cx="80" cy="25" r="2.5" fill="currentColor" className="spinner-dot dot-2" />
        <circle cx="80" cy="60" r="2.5" fill="currentColor" className="spinner-dot dot-3" />
        <circle cx="50" cy="75" r="2.5" fill="currentColor" className="spinner-dot dot-4" />
        <circle cx="20" cy="60" r="2.5" fill="currentColor" className="spinner-dot dot-5" />
        <circle cx="20" cy="25" r="2.5" fill="currentColor" className="spinner-dot dot-6" />
      </svg>

      {message && <p className="loading-message">{message}</p>}
    </div>
  );
};

export default LoadingSpinner;
