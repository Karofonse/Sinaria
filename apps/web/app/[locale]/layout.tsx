import { notFound } from "next/navigation";
import { I18nProvider } from "@/components/i18n-provider";
import { Footer, Nav } from "@/components/nav";
import { getMessages, isLocale, lookup } from "@/lib/i18n";

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const messages = await getMessages(locale);
  return (
    <I18nProvider locale={locale} messages={messages}>
      <a href="#contenido" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-full focus:bg-lavender focus:px-4 focus:py-2 focus:text-midnight">
        {lookup(messages, "common.skip")}
      </a>
      <Nav />
      <main id="contenido" className="min-h-[70dvh]">
        {children}
      </main>
      <Footer />
    </I18nProvider>
  );
}
