"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Me } from "@/lib/types";

export type SessionState =
  | { status: "loading" }
  | { status: "anonymous" }
  | { status: "authenticated"; me: Me };

/** Carga la sesión desde la API. La API decide; el cliente solo refleja su respuesta. */
export function useSession(): SessionState & { refresh: () => void } {
  const [state, setState] = useState<SessionState>({ status: "loading" });
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api<Me>("/v1/auth/me")
      .then((me) => !cancelled && setState({ status: "authenticated", me }))
      .catch((err: unknown) => {
        // 401 y 403 significan "no autenticado" para la interfaz. Cualquier otro fallo también la trata
        // como anónima: la página protegida vuelve a pedir la sesión al servidor antes de mostrar datos.
        if (cancelled) return;
        void (err instanceof ApiError);
        setState({ status: "anonymous" });
      });
    return () => {
      cancelled = true;
    };
  }, [nonce]);

  return { ...state, refresh: () => setNonce((n) => n + 1) };
}
