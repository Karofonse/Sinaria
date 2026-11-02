import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-[70dvh] max-w-md flex-col items-center justify-center gap-4 px-4 text-center">
      <p className="text-sm tracking-widest text-lavender">404</p>
      <h1 className="text-3xl font-semibold text-white">Página no encontrada</h1>
      <p className="text-mist">La dirección no existe o se ha movido. · The address does not exist or has moved.</p>
      <Link href="/es" className="mt-2 rounded-full bg-lavender px-5 py-2.5 font-medium text-midnight hover:bg-lavender-soft">
        Volver al inicio · Back to home
      </Link>
    </main>
  );
}
