/**
 * 404 Not Found — Cyber Hive broken patch cable
 */
import { Link } from "react-router-dom";
import "./NotFound.css";

export default function NotFound() {
  return (
    <div className="not-found-container">
      <div className="not-found-content">
        <svg
          width="360"
          height="360"
          viewBox="0 0 400 400"
          xmlns="http://www.w3.org/2000/svg"
          className="broken-patch"
          aria-hidden="true"
        >
          <defs>
            <linearGradient id="cable-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="var(--ph-amber, #f5a623)" />
              <stop offset="100%" stopColor="var(--ph-cyan, #3ddcff)" />
            </linearGradient>
          </defs>

          <path
            d="M 200,40 L 330,110 L 330,180"
            fill="none"
            stroke="var(--ph-danger, #e23d4a)"
            strokeWidth="3"
          />
          <path
            d="M 330,220 L 330,250 L 200,320 L 70,250 L 70,110 L 130,75"
            fill="none"
            stroke="var(--ph-danger, #e23d4a)"
            strokeWidth="3"
          />
          <path
            d="M 330,180 L 340,185 L 335,195 L 330,220"
            fill="none"
            stroke="var(--ph-danger, #e23d4a)"
            strokeWidth="2"
            strokeDasharray="3,3"
            opacity="0.6"
          />

          <path
            d="M 100,150 Q 120,170 150,180 T 180,190"
            fill="none"
            stroke="url(#cable-gradient)"
            strokeWidth="4"
            strokeLinecap="round"
            className="cable-left"
          />
          <circle cx="100" cy="150" r="8" fill="var(--ph-amber, #f5a623)" />
          <circle cx="100" cy="150" r="4" fill="var(--zs-carbon, #08090b)" />

          <path
            d="M 300,150 Q 280,170 250,180 T 220,190"
            fill="none"
            stroke="url(#cable-gradient)"
            strokeWidth="4"
            strokeLinecap="round"
            className="cable-right"
          />
          <circle cx="300" cy="150" r="8" fill="var(--ph-cyan, #3ddcff)" />
          <circle cx="300" cy="150" r="4" fill="var(--zs-carbon, #08090b)" />

          <text
            x="200"
            y="280"
            fill="var(--ph-amber, #f5a623)"
            fontFamily="var(--font-mono, ui-monospace, monospace)"
            fontSize="72"
            fontWeight="bold"
            textAnchor="middle"
          >
            404
          </text>
        </svg>

        <p className="eyebrow">Signal loss</p>
        <h1 className="error-title">Patch not found</h1>
        <p className="error-description">
          The route you requested has been disconnected or never existed in this hive.
        </p>

        <div className="error-actions">
          <Link to="/" className="button button-primary">
            Return home
          </Link>
          <Link to="/modules" className="button button-secondary">
            Browse modules
          </Link>
          <Link to="/racks" className="button button-quiet">
            Open rigs
          </Link>
        </div>

        <div className="error-details">
          <code>ERROR_CODE: PATCH_DISCONNECTED</code>
          <code>STATUS: 404 NOT_FOUND</code>
          <code>SUGGESTED_ACTION: RECONNECT_OR_RETURN_HOME</code>
        </div>
      </div>
    </div>
  );
}
