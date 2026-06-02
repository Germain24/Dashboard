"use client";

/**
 * Error boundary réutilisable par module — capture les erreurs de rendu d'une
 * sous-arborescence sans faire planter toute la page.
 *
 * Usage :
 *   <ErrorBoundary label="Finance"><Finance /></ErrorBoundary>
 */

import { Component, type ReactNode } from "react";

type Props = { children: ReactNode; label?: string; fallback?: ReactNode };
type State = { error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error(`[ErrorBoundary${this.props.label ? ` ${this.props.label}` : ""}]`, error);
  }

  reset = () => this.setState({ error: null });

  render() {
    if (this.state.error) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="m-6 rounded-xl border border-[var(--destructive)]/30 bg-[color-mix(in_srgb,var(--destructive)_8%,transparent)] p-6 text-sm">
          <p className="font-medium text-[var(--destructive)]">
            {this.props.label ? `Erreur dans « ${this.props.label} »` : "Une erreur est survenue"}
          </p>
          <p className="mt-1 text-[var(--muted-foreground)]">{this.state.error.message}</p>
          <button
            onClick={this.reset}
            className="mt-3 rounded-md border border-[var(--border)] px-3 py-1.5 text-xs hover:bg-[var(--muted)]"
          >
            Réessayer
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
