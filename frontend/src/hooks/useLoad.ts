import { useCallback, useEffect, useState } from "react";

interface Result<T> {
  load: unknown;
  attempt: number;
  data?: T;
  error?: Error;
}

/** Carrega dados e cancela a busca quando ela deixa de interessar. `load` deve ser estável. */
export function useLoad<T>(load: (signal: AbortSignal) => Promise<T>) {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<Result<T> | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setResult({ load, attempt, data });
      },
      (error: unknown) => {
        if (controller.signal.aborted) return;
        setResult({
          load,
          attempt,
          error: error instanceof Error ? error : new Error("Erro inesperado."),
        });
      },
    );
    return () => controller.abort();
  }, [load, attempt]);

  const current = result?.load === load && result.attempt === attempt ? result : null;
  const reload = useCallback(() => setAttempt((value) => value + 1), []);
  const setData = useCallback((data: T) => setResult({ load, attempt, data }), [load, attempt]);
  return { data: current?.data, error: current?.error, loading: current === null, reload, setData };
}
