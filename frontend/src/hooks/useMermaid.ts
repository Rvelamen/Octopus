import { useEffect, useState, useRef, useCallback } from 'react';

type MermaidApi = any; // dynamically imported mermaid module

let mermaidModule: MermaidApi | null = null;
let mermaidLoading = false;
let mermaidLoadPromise: Promise<MermaidApi> | null = null;

const loadMermaidModule = async (): Promise<MermaidApi> => {
  if (mermaidModule) return mermaidModule;
  if (mermaidLoading && mermaidLoadPromise) return mermaidLoadPromise;

  mermaidLoading = true;
  mermaidLoadPromise = import('mermaid')
    .then((module) => {
      mermaidModule = module.default || module;
      mermaidLoading = false;
      return mermaidModule;
    })
    .catch((error: unknown) => {
      mermaidLoading = false;
      throw error;
    });

  return mermaidLoadPromise;
};

const getIsDarkMode = (): boolean => {
  if (typeof document === 'undefined') return false;
  return document.documentElement.classList.contains('dark');
};

interface UseMermaidReturn {
  mermaid: MermaidApi | null;
  isLoading: boolean;
  error: string | null;
  forceRenderKey: number;
}

export function useMermaid(): UseMermaidReturn {
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [forceRenderKey, setForceRenderKey] = useState<number>(0);
  const observerRef = useRef<MutationObserver | null>(null);

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
