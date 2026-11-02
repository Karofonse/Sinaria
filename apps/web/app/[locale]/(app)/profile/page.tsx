"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useI18n } from "@/components/i18n-provider";
import { Button, Card, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";

export default function ProfilePage() {
  const { t, locale } = useI18n();
  const router = useRouter();
  const session = useSession();

  async function logout() {
    await api<void>("/v1/auth/logout", { method: "POST" }).catch(() => undefined);
    router.push(`/${locale}/login`);
  }

  function setLocale(next: "es" | "en") {
    document.cookie = `sonaria_locale=${next}; path=/; max-age=31536000; samesite=lax`;
    router.push(`/${next}/profile`);
  }

  if (session.status !== "authenticated") return <Spinner label={t("common.loading")} />;
  const me = session.me;

  return (
    <>
      <PageHeader title={t("profile.title")} />
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <h2 className="mb-4 font-medium text-white">{t("profile.account")}</h2>
          <dl className="space-y-4 text-sm">
            <div>
              <dt className="text-mist">{t("profile.name")}</dt>
              <dd className="text-white">{me.display_name}</dd>
            </div>
            <div>
              <dt className="text-mist">{t("profile.email")}</dt>
              <dd className="break-all text-white">{me.email}</dd>
            </div>
            <div>
              <dt className="text-mist">{t("profile.roles")}</dt>
              <dd className="text-white">{me.roles.join(", ")}</dd>
            </div>
          </dl>
        </Card>
        <Card className="space-y-5">
          <div>
            <p className="mb-3 text-sm font-medium text-lavender-soft">{t("profile.locale")}</p>
            <div className="flex gap-2" role="group" aria-label={t("profile.locale")}>
              <Button variant={locale === "es" ? "primary" : "secondary"} aria-pressed={locale === "es"} onClick={() => setLocale("es")}>Español</Button>
              <Button variant={locale === "en" ? "primary" : "secondary"} aria-pressed={locale === "en"} onClick={() => setLocale("en")}>English</Button>
            </div>
          </div>
          <div>
            <p className="mb-3 text-sm text-mist">{t("profile.logoutHint")}</p>
            <Button variant="danger" onClick={logout}>{t("nav.logout")}</Button>
          </div>
          <Link href={`/${locale}/dashboard`} className="inline-block text-sm text-lavender hover:underline">{t("nav.dashboard")} →</Link>
        </Card>
      </div>
    </>
  );
}
