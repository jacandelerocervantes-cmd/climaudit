"use client";

import { useCallback, useRef, useState } from "react";
import { api, ApiFailure, newIdempotencyKey, type ApiInit } from "@/lib/client/api";

/**
 * Runs one state-changing call. The Idempotency-Key is kept while the request body stays the same, so a retry after a
 * timeout or an outage cannot repeat the action; a changed body starts a new intent with a new key.
 */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiFailure | null>(null);
  const memo = useRef<{ signature: string; key: string } | null>(null);

  const run = useCallback(async <T,>(path: string, body: unknown, method: ApiInit["method"] = "POST"): Promise<T | null> => {
    const signature = `${method} ${path} ${JSON.stringify(body ?? null)}`;
    if (memo.current?.signature !== signature) memo.current = { signature, key: newIdempotencyKey() };
    setBusy(true);
    setError(null);
    try {
      const result = await api<T>(path, { method, body, idempotencyKey: memo.current.key });
      memo.current = null;
      return result;
    } catch (failure) {
      setError(failure instanceof ApiFailure ? failure : new ApiFailure("INTERNAL_ERROR", 0));
      return null;
    } finally {
      setBusy(false);
    }
  }, []);

  const clear = useCallback(() => setError(null), []);
  return { run, busy, error, clear };
}
