import { notFound } from "next/navigation";
import { PageHeader, Notice } from "@/components/ui";
import { getMessages, isLocale, lookup } from "@/lib/i18n";

export default async function TermsPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const m = await getMessages(locale);
  return (
    <article className="mx-auto max-w-3xl space-y-6 px-4 py-12">
      <PageHeader title={lookup(m, "legal.termsTitle")} />
      <Notice tone="warning">{lookup(m, "legal.draftNotice")}</Notice>
      <ol className="list-decimal space-y-3 pl-5 text-lavender-soft">
        {["terms_1", "terms_2", "terms_3", "terms_4"].map((k) => (
          <li key={k}>{lookup(m, `legal.${k}`)}</li>
        ))}
      </ol>
    </article>
  );
}
