import { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback: ReactNode;
}

interface State {
  hasError: boolean;
}

/** Defense in depth: MapView already catches its own known WebGL-init
 * failure mode (see its own comment), but a class component error boundary
 * is the only mechanism React actually provides for catching anything
 * ELSE unexpected in the render tree, so a single bad GeoJSON edge case or
 * a MapLibre internal bug can't blank the entire app for a judge mid-demo.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    console.error('[ErrorBoundary]', error);
  }

  render() {
    if (this.state.hasError) return this.props.fallback;
    return this.props.children;
  }
}
