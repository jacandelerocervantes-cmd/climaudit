"use client";

import { useCallback, useEffect, useState } from "react";

/** A failed API call: the error envelope of the backend (`{error: {code, params, correlation_id}}`) or a transport failure. */
export class ApiFailure extends Error {
  readonly code: string;
  readonly status: number;
  readonly params: Record<string, unknown>;
  readonly correlationId: string | null;

  constructor(code: string, status: number, params: Record<string, unknown> = {}, correlationId: string | null = null) {
    super(code);
    this.code = code;
    this.status = status;
    this.params = params;
    this.correlationId = correlationId;
  }
}

type Envelope = { error?: { code?: unknown; params?: unknown; correlation_id?: unknown } };

export function parseFailure(status: number, text: string): ApiFailure {
  try {
    const body = JSON.parse(text) as Envelope;
    const code = typeof body.error?.code === "string" ? body.error.code : null;
    if (code) {
      const params = typeof body.error?.params === "object" && body.error.params !== null ? (body.error.params as Record<string, unknown>) : {};
      const correlation = typeof body.error?.correlation_id === "string" ? body.error.correlation_id : null;
      return new ApiFailure(code, status, params, correlation);
    }
  } catch {
    // not JSON: fall through to a generic failure
  }
  return new ApiFailure(status >= 500 ? "INTERNAL_ERROR" : "VALIDATION_FAILED", status, { reason: "unreadable_response" });
}

export function newIdempotencyKey(): string {
  return globalThis.crypto.randomUUID();
}

export type ApiInit = { method?: "GET" | "POST" | "PUT"; body?: unknown; idempotencyKey?: string };

/** Calls the ClimAudit API through the same-origin proxy. State-changing calls always carry an Idempotency-Key. */
export async function api<T>(path: string, init: ApiInit = {}): Promise<T> {
  const method = init.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json" };
  if (init.body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") headers["Idempotency-Key"] = init.idempotencyKey ?? newIdempotencyKey();
  let response: Response;
  try {
    response = await fetch(`/api/cp/${path.replace(/^\/+/, "")}`, { method, headers, body: init.body === undefined ? undefined : JSON.stringify(init.body), cache: "no-store" });
  } catch {
    throw new ApiFailure("API_UNREACHABLE", 0, { reason: "network" });
  }
  const text = await response.text();
  if (!response.ok) throw parseFailure(response.status, text);
  return (text ? JSON.parse(text) : null) as T;
}

export type ApiState<T> = { data: T | null; error: ApiFailure | null; loading: boolean; refreshing: boolean; reload: () => void };

type Settled<T> = { key: string; hard: string; data: T | null; error: ApiFailure | null };

/**
 * Loads a GET route; pass `null` to stay idle. A change of `path` or `refreshKey` starts from scratch (`loading`); a
 * `reload()` keeps showing the previous data while the new answer arrives (`refreshing`), so screens do not flash empty
 * and the state of a form or a confirmation message next to the data is not lost.
 */
export function useApi<T>(path: string | null, refreshKey: unknown = 0): ApiState<T> {
  const [tick, setTick] = useState(0);
  const [settled, setSettled] = useState<Settled<T> | null>(null);
  const hardKey = path === null ? null : `${path}|${String(refreshKey)}`;
  const requestKey = hardKey === null ? null : `${hardKey}|${tick}`;

  useEffect(() => {
    if (path === null || requestKey === null || hardKey === null) return;
    let alive = true;
    api<T>(path)
      .then((data) => {
        if (alive) setSettled({ key: requestKey, hard: hardKey, data, error: null });
      })
      .catch((error: unknown) => {
        if (alive) setSettled({ key: requestKey, hard: hardKey, data: null, error: error instanceof ApiFailure ? error : new ApiFailure("INTERNAL_ERROR", 0) });
      });
    return () => {
      alive = false;
    };
  }, [path, requestKey, hardKey]);

  const reload = useCallback(() => setTick((n) => n + 1), []);
  const current = settled !== null && settled.key === requestKey ? settled : null;
  const stale = settled !== null && settled.hard === hardKey && settled.data !== null ? settled : null;
  return {
    data: (current ?? stale)?.data ?? null,
    error: current?.error ?? null,
    loading: requestKey !== null && current === null && stale === null,
    refreshing: requestKey !== null && current === null && stale !== null,
    reload,
  };
}
