"use client";

import { useEffect } from "react";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    // Sin datos personales: solo se registra el identificador de la excepción de Next.js.
    console.error("ui_error", error.digest ?? "unknown");
  }, [error]);

  return (
    <main className="mx-auto flex min-h-[70dvh] max-w-md flex-col items-center justify-center gap-4 px-4 text-center" role="alert">
      <h1 className="text-3xl font-semibold text-white">Algo ha fallado · Something went wrong</h1>
      <p className="text-mist">Hemos registrado el error. Puedes intentarlo de nuevo. · We logged the error. You can try again.</p>
      <button
        type="button"
        onClick={() => reset()}
        className="mt-2 rounded-full bg-lavender px-5 py-2.5 font-medium text-midnight hover:bg-lavender-soft"
      >
        Reintentar · Retry
      </button>
    </main>
  );
}
