"use client";

import { useRouter, usePathname } from "next/navigation";
import { useEffect } from "react";
import { useI18n } from "@/components/i18n-provider";
import { Spinner } from "@/components/ui";
import { useSession } from "@/lib/session";

/** Protege las páginas autenticadas en la interfaz. La API vuelve a comprobar cada operación. */
export function AppShell({ children }: { children: React.ReactNode }) {
  const { t, locale } = useI18n();
  const router = useRouter();
  const pathname = usePathname();
  const session = useSession();

  useEffect(() => {
    if (session.status === "anonymous") {
      router.replace(`/${locale}/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [session.status, locale, pathname, router]);

  if (session.status !== "authenticated") {
    return (
      <div className="mx-auto max-w-6xl px-4 py-16">
        <Spinner label={t("common.loading")} />
      </div>
    );
  }
  return <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:py-10">{children}</div>;
}
