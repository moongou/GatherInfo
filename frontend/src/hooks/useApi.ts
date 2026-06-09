import { useState, useEffect, useCallback, useRef } from "react";

interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

interface UseApiReturn<T> extends UseApiState<T> {
  /** Re-execute the fetch. Returns the fresh data on success, null on failure. */
  refresh: () => Promise<T | null>;
  /** Manually set data (optimistic updates). */
  setData: (data: T | null) => void;
}

/**
 * Generic async data-fetching hook.
 *
 * Usage:
 *   const { data, loading, error, refresh } = useApi(() => fetchDashboard());
 *
 * Features:
 * - Cancels stale in-flight requests on unmount / re-fetch
 * - `refresh()` can be called imperatively (e.g. after a mutation)
 * - `loading` is true on initial fetch; stays false on refresh for smoother UX (configurable)
 */
export function useApi<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: unknown[] = [],
  opts: { showLoadingOnRefresh?: boolean } = {},
): UseApiReturn<T> {
  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    loading: true,
    error: null,
  });
  const mountedRef = useRef(true);

  const execute = useCallback(
    async (isInitial: boolean): Promise<T | null> => {
      const controller = new AbortController();

      if (isInitial || opts.showLoadingOnRefresh) {
        setState((s) => ({ ...s, loading: true, error: null }));
      }

      try {
        const result = await fetcher(controller.signal);
        if (mountedRef.current && !controller.signal.aborted) {
          setState({ data: result, loading: false, error: null });
        }
        return result;
      } catch (e: unknown) {
        if (controller.signal.aborted) return null;
        const msg = e instanceof Error ? e.message : "Unknown error";
        if (mountedRef.current) {
          setState((s) => ({ ...s, loading: false, error: msg }));
        }
        return null;
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    deps,
  );

  useEffect(() => {
    mountedRef.current = true;
    void execute(true);
    return () => {
      mountedRef.current = false;
    };
  }, [execute]);

  const refresh = useCallback(() => execute(false), [execute]);

  return { ...state, refresh, setData: (d) => setState((s) => ({ ...s, data: d })) };
}
