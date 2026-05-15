import { useEffect, useState, useRef, useCallback } from 'react';

let mermaidModule = null;
let mermaidLoading = false;
let mermaidLoadPromise = null;

const loadMermaidModule = async () => {
  if (mermaidModule) return mermaidModule;
  if (mermaidLoading && mermaidLoadPromise) return mermaidLoadPromise;

  mermaidLoading = true;
  mermaidLoadPromise = import('mermaid')
    .then((module) => {
      mermaidModule = module.default || module;
      mermaidLoading = false;
      return mermaidModule;
    })
    .catch((error) => {
      mermaidLoading = false;
      throw error;
    });

  return mermaidLoadPromise;
};

const getIsDarkMode = () => {
  if (typeof document === 'undefined') return false;
  return document.documentElement.classList.contains('dark');
};

export function useMermaid() {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [forceRenderKey, setForceRenderKey] = useState(0);
  const observerRef = useRef(null);

  const initialize = useCallback(async () => {
    try {
      setIsLoading(true);
      const mermaid = await loadMermaidModule();
      mermaid.initialize({
        startOnLoad: false,
        theme: getIsDarkMode() ? 'dark' : 'default',
      });
      setForceRenderKey((prev) => prev + 1);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to initialize Mermaid');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    initialize().then(() => {
      if (!mounted) return;
      // Watch for dark mode changes
      const target = document.documentElement;
      observerRef.current = new MutationObserver(() => {
        initialize();
      });
      observerRef.current.observe(target, { attributes: true, attributeFilter: ['class'] });
    });
    return () => {
      mounted = false;
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
    };
  }, [initialize]);

  return {
    mermaid: mermaidModule,
    isLoading,
    error,
    forceRenderKey,
  };
}
