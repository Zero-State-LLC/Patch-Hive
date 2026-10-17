/**
 * PatchHive Animated Logo Component
 * Pulsing oscillator core with rotating CV pathways
 */
import React from "react";
import "./AnimatedLogo.css";

interface AnimatedLogoProps {
  size?: number;
  animate?: boolean;
}

export const AnimatedLogo: React.FC<AnimatedLogoProps> = ({ size = 200, animate = true }) => {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 400 400"
      xmlns="http://www.w3.org/2000/svg"
      className={animate ? "patchhive-logo-animated" : "patchhive-logo-static"}
    >
      <defs>
        <filter id="glow-animated">
          <feGaussianBlur stdDeviation="4" result="coloredBlur" />
          <feMerge>
            <feMergeNode in="coloredBlur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>

        <pattern
          id="honeycomb-animated"
          x="0"
          y="0"
          width="30"
          height="26"
          patternUnits="userSpaceOnUse"
        >
          <polygon
            points="15,0 27,7.5 27,20.5 15,28 3,20.5 3,7.5"
            fill="none"
            stroke="#f5a623"
            strokeWidth="0.5"
            opacity="0.15"
          />
        </pattern>
      </defs>

      {/* Outer hexagon */}
      <polygon
        points="200,40 330,110 330,250 200,320 70,250 70,110"
        fill="none"
        stroke="#f5a623"
        strokeWidth="3"
        filter="url(#glow-animated)"
        className="hex-outer"
      />

      {/* Honeycomb interior fill */}
      <polygon
        points="200,40 330,110 330,250 200,320 70,250 70,110"
        fill="url(#honeycomb-animated)"
      />

      {/* Inner hex frame */}
      <polygon
        points="200,80 290,130 290,230 200,280 110,230 110,130"
        fill="none"
        stroke="#f5a623"
        strokeWidth="2"
        opacity="0.6"
        className="hex-inner"
      />

      {/* Central luminous core - pulsing */}
      <circle cx="200" cy="180" r="35" fill="#f5a623" opacity="0.3" className="core-outer" />
      <circle cx="200" cy="180" r="25" fill="#f5a623" opacity="0.5" className="core-middle" />
      <circle
        cx="200"
        cy="180"
        r="15"
        fill="#f5a623"
        filter="url(#glow-animated)"
        className="core-inner"
      />

      {/* CV Pathways - rotating group */}
      <g className="cv-pathways">
        <path
          d="M 200,180 Q 240,160 260,140 T 290,110"
          fill="none"
          stroke="#f5a623"
          strokeWidth="2.5"
          strokeLinecap="round"
          filter="url(#glow-animated)"
          className="pathway-1"
        />
        <path
          d="M 200,180 Q 160,200 140,220 T 110,250"
          fill="none"
          stroke="#f5a623"
          strokeWidth="2.5"
          strokeLinecap="round"
          filter="url(#glow-animated)"
          className="pathway-2"
        />
        <path
          d="M 200,180 Q 230,180 260,170 T 300,180"
          fill="none"
          stroke="#f5a623"
          strokeWidth="2.5"
          strokeLinecap="round"
          filter="url(#glow-animated)"
          className="pathway-3"
        />
      </g>

      {/* Signal dots - traveling */}
      <circle cx="230" cy="165" r="3" fill="#f5a623" className="signal-dot dot-1" />
      <circle cx="170" cy="195" r="3" fill="#f5a623" className="signal-dot dot-2" />
      <circle cx="250" cy="175" r="3" fill="#f5a623" className="signal-dot dot-3" />

      {/* Voltage markers */}
      <polygon points="200,40 207,44 207,52 200,56 193,52 193,44" fill="#f5a623" opacity="0.8" />
      <polygon
        points="330,110 337,114 337,122 330,126 323,122 323,114"
        fill="#f5a623"
        opacity="0.8"
      />
      <polygon
        points="330,250 337,254 337,262 330,266 323,262 323,254"
        fill="#f5a623"
        opacity="0.8"
      />
      <polygon
        points="200,320 207,324 207,332 200,336 193,332 193,324"
        fill="#f5a623"
        opacity="0.8"
      />
      <polygon points="70,250 77,254 77,262 70,266 63,262 63,254" fill="#f5a623" opacity="0.8" />
      <polygon points="70,110 77,114 77,122 70,126 63,122 63,114" fill="#f5a623" opacity="0.8" />
    </svg>
  );
};

export default AnimatedLogo;
