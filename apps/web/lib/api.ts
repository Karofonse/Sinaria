/** Cliente de la API. Siempre same-origin: el rewrite de next.config.ts envía /v1 al backend. */

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type ApiInit = Omit<RequestInit, "body"> & { json?: unknown; idempotencyKey?: string };

export async function api<T>(path: string, init: ApiInit = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (init.json !== undefined) headers["Content-Type"] = "application/json";
  if (init.idempotencyKey) headers["Idempotency-Key"] = init.idempotencyKey;

  const res = await fetch(path, {
    ...init,
    method: init.method ?? (init.json !== undefined ? "POST" : "GET"),
    credentials: "same-origin",
    cache: "no-store",
    headers,
    body: init.json !== undefined ? JSON.stringify(init.json) : undefined,
  });

  if (res.status === 204) return undefined as T;
  const data: unknown = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = (data as { detail?: { code?: string; message?: string } } | null)?.detail;
    throw new ApiError(res.status, detail?.code ?? "error", detail?.message ?? `HTTP ${res.status}`);
  }
  return data as T;
}

export function newIdempotencyKey(): string {
  return crypto.randomUUID();
}
