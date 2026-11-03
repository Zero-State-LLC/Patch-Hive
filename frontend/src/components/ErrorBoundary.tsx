/**
 * ErrorBoundary — a screen that fails to render shows a way out instead of blanking the app.
 * RouteErrorBoundary resets on navigation, so leaving the broken screen clears the error.
 */
import { Component } from "react";
import type { ReactNode } from "react";
import { useLocation } from "react-router-dom";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  // React itself reports the error to the console; this only swaps in the fallback.
  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <section className="screen-state" role="alert" aria-labelledby="screen-error-title">
        <h1 id="screen-error-title" className="empty-title">
          This screen stopped working
        </h1>
        <p>Something on it failed to draw. Reload to try again, or go back to the start.</p>
        <div className="screen-state-actions">
          <button
            className="button button-primary"
            type="button"
            onClick={() => window.location.reload()}
          >
            Reload
          </button>
          <a className="button button-secondary" href="/">
            Go home
          </a>
        </div>
      </section>
    );
  }
}

export function RouteErrorBoundary({ children }: Props) {
  const { pathname } = useLocation();
  return <ErrorBoundary key={pathname}>{children}</ErrorBoundary>;
}
