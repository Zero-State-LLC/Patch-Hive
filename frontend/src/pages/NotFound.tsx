/**
 * 404 Not Found — Cyber Hive broken patch cable
 */
import { Link, useLocation } from "react-router-dom";
import "./NotFound.css";

export default function NotFound() {
  const { pathname } = useLocation();
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
              <stop offset="0%" stopColor="var(--cable-audio)" />
              <stop offset="100%" stopColor="var(--cable-cv)" />
            </linearGradient>
          </defs>

          <path
            d="M 200,40 L 330,110 L 330,180"
            fill="none"
            stroke="var(--color-rule-strong)"
            strokeWidth="3"
          />
          <path
            d="M 330,220 L 330,250 L 200,320 L 70,250 L 70,110 L 130,75"
            fill="none"
            stroke="var(--color-rule-strong)"
            strokeWidth="3"
          />
          <path
            d="M 330,180 L 340,185 L 335,195 L 330,220"
            fill="none"
            stroke="var(--color-rule-strong)"
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
          <circle cx="100" cy="150" r="8" fill="var(--cable-audio)" />
          <circle cx="100" cy="150" r="4" fill="var(--color-paper)" />

          <path
            d="M 300,150 Q 280,170 250,180 T 220,190"
            fill="none"
            stroke="url(#cable-gradient)"
            strokeWidth="4"
            strokeLinecap="round"
            className="cable-right"
          />
          <circle cx="300" cy="150" r="8" fill="var(--cable-cv)" />
          <circle cx="300" cy="150" r="4" fill="var(--color-paper)" />

          <text
            x="200"
            y="280"
            fill="var(--color-signal)"
            fontFamily="var(--font-mono)"
            fontSize="72"
            fontWeight="500"
            textAnchor="middle"
          >
            404
          </text>
        </svg>

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

        <p className="error-details">
          Nothing lives at <code>{pathname}</code>.
        </p>
      </div>
    </div>
  );
}
