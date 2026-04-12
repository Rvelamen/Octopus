import React from 'react';
import { AlertCircle } from "lucide-react";

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({
      error: error,
      errorInfo: errorInfo,
    });
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="error-boundary">
          <div className="error-boundary-content">
            <AlertCircle size={48} className="error-boundary-icon" />
            <h2 className="error-boundary-title">
              {this.props.title || "出现了一些问题"}
            </h2>
            <p className="error-boundary-message">
              {this.props.message || "页面遇到了意外错误，请尝试刷新页面或联系技术支持。"}
            </p>
            {this.state.error && process.env.NODE_ENV === 'development' && (
              <details className="error-boundary-details">
                <summary>错误详情</summary>
                <pre>{this.state.error.toString()}</pre>
                <pre>{this.state.errorInfo?.componentStack}</pre>
              </details>
            )}
            <div className="error-boundary-actions">
              <button className="error-boundary-button" onClick={this.handleReset}>
                重试
              </button>
              <button
                className="error-boundary-button secondary"
                onClick={() => window.location.reload()}
              >
                刷新页面
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
