"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { useI18n } from "@/components/i18n-provider";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";

export function Nav() {
  const { t, locale } = useI18n();
  const router = useRouter();
  const pathname = usePathname();
  const session = useSession();
  const [open, setOpen] = useState(false);
  const base = `/${locale}`;
  const authed = session.status === "authenticated";
  const isAdmin = authed && session.me.roles.includes("admin");

  const links = authed
    ? [
        { href: `${base}/studio`, label: t("nav.studio") },
        { href: `${base}/library`, label: t("nav.library") },
        { href: `${base}/dashboard`, label: t("nav.dashboard") },
        { href: `${base}/billing`, label: t("nav.billing") },
        ...(isAdmin ? [{ href: `${base}/admin`, label: t("nav.admin") }] : []),
        { href: `${base}/profile`, label: t("nav.profile") },
      ]
    : [];

  async function logout() {
    try {
      await api<void>("/v1/auth/logout", { method: "POST" });
    } finally {
      session.refresh();
      router.push(`${base}/login`);
    }
  }

  const otherLocale = locale === "es" ? "en" : "es";
  const switchPath = pathname.replace(`/${locale}`, `/${otherLocale}`);

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-midnight/75 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <Link href={base} className="flex items-center gap-2 font-semibold tracking-tight text-white" aria-label={t("common.appName")}>
          <svg width="26" height="26" viewBox="0 0 26 26" aria-hidden>
            <defs>
              <linearGradient id="sg" x1="0" x2="1" y1="0" y2="1">
                <stop offset="0" stopColor="#c9b8ff" />
                <stop offset="1" stopColor="#5b3aa8" />
              </linearGradient>
            </defs>
            <rect width="26" height="26" rx="8" fill="url(#sg)" />
            <path d="M6 13h2l2-5 3 10 3-7 2 2h2" fill="none" stroke="#0a0e22" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          {t("common.appName")}
        </Link>

        <nav aria-label="Principal" className="hidden items-center gap-1 md:flex">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              aria-current={pathname.startsWith(l.href) ? "page" : undefined}
              className={`rounded-full px-3 py-2 text-sm transition-colors ${pathname.startsWith(l.href) ? "bg-surface-2 text-white" : "text-mist hover:text-white"}`}
            >
              {l.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <Link href={switchPath} className="rounded-full px-3 py-2 text-xs text-mist ring-1 ring-line hover:text-white" hrefLang={otherLocale} lang={otherLocale}>
            {otherLocale.toUpperCase()}
          </Link>
          {authed ? (
            <button type="button" onClick={logout} className="hidden rounded-full px-4 py-2 text-sm text-mist hover:text-white md:inline-block">
              {t("nav.logout")}
            </button>
          ) : session.status === "anonymous" ? (
            <div className="hidden items-center gap-2 md:flex">
              <Link href={`${base}/login`} className="rounded-full px-4 py-2 text-sm text-mist hover:text-white">
                {t("nav.login")}
              </Link>
              <Link href={`${base}/register`} className="rounded-full bg-lavender px-4 py-2 text-sm font-medium text-midnight hover:bg-lavender-soft">
                {t("nav.register")}
              </Link>
            </div>
          ) : null}
          <button
            type="button"
            className="rounded-full p-2 text-mist ring-1 ring-line md:hidden"
            aria-expanded={open}
            aria-controls="mobile-menu"
            aria-label={t("nav.menu")}
            onClick={() => setOpen((v) => !v)}
          >
            <span aria-hidden>{open ? "✕" : "☰"}</span>
          </button>
        </div>
      </div>

      {open ? (
        <nav id="mobile-menu" aria-label="Principal móvil" className="border-t border-line px-4 py-3 md:hidden">
          <ul className="grid gap-1">
            {(authed ? links : []).map((l) => (
              <li key={l.href}>
                <Link href={l.href} onClick={() => setOpen(false)} className="block rounded-xl px-3 py-3 text-mist hover:bg-surface-2 hover:text-white">
                  {l.label}
                </Link>
              </li>
            ))}
            {authed ? (
              <li>
                <button type="button" onClick={logout} className="block w-full rounded-xl px-3 py-3 text-left text-mist hover:bg-surface-2 hover:text-white">
                  {t("nav.logout")}
                </button>
              </li>
            ) : (
              <>
                <li>
                  <Link href={`${base}/login`} onClick={() => setOpen(false)} className="block rounded-xl px-3 py-3 text-mist hover:bg-surface-2">
                    {t("nav.login")}
                  </Link>
                </li>
                <li>
                  <Link href={`${base}/register`} onClick={() => setOpen(false)} className="block rounded-xl px-3 py-3 text-lavender hover:bg-surface-2">
                    {t("nav.register")}
                  </Link>
                </li>
              </>
            )}
          </ul>
        </nav>
      ) : null}
    </header>
  );
}

export function Footer() {
  const { t, locale } = useI18n();
  return (
    <footer className="mt-16 border-t border-line">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-8 text-sm text-mist sm:flex-row sm:items-center sm:justify-between">
        <p>{t("footer.rights", { year: new Date().getFullYear() })}</p>
        <p className="text-xs">{t("footer.draft")}</p>
        <div className="flex gap-4">
          <Link href={`/${locale}/terms`} className="hover:text-white">
            {t("footer.terms")}
          </Link>
          <Link href={`/${locale}/privacy`} className="hover:text-white">
            {t("footer.privacy")}
          </Link>
        </div>
      </div>
    </footer>
  );
}
