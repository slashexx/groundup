import { Component } from 'react';

/**
 * Keeps one broken page from taking the whole application with it.
 *
 * React unmounts the entire tree when a render throws and nothing catches it — not just
 * the failing branch. A single bad reference in the 3D scene blanked every other screen,
 * including ones that were perfectly healthy, and the symptom looked nothing like its
 * cause: the app appeared to die on whatever page you happened to open next.
 *
 * A failure here is shown, named, and confined to the panel that failed. It is never
 * swallowed — a page that quietly renders nothing is the same lie as a clean bill of
 * health on a project nobody validated.
 */
export default class PageBoundary extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // The stack is the only place the real cause is written down; the panel below shows
    // the message, and this keeps the trace reachable in devtools.
    console.error('page failed to render', error, info?.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div className="page-boundary">
        <div className="page-boundary-title">This screen failed to render</div>
        <div className="page-boundary-message">{String(this.state.error.message ?? this.state.error)}</div>
        <div className="page-boundary-note">
          The rest of the application is unaffected, and the project on disk has not been
          touched — nothing here writes on render. Pick another screen from the menu, or
          retry this one.
        </div>
        <button className="btn btn-secondary btn-sm"
                onClick={() => this.setState({ error: null })}>
          Retry this screen
        </button>
      </div>
    );
  }
}
