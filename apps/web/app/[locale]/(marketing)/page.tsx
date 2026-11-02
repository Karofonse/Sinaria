import Link from "next/link";
import { notFound } from "next/navigation";
import { ButtonLink, Card } from "@/components/ui";
import { getMessages, isLocale, lookup, type Messages } from "@/lib/i18n";

const STYLE_KEYS = ["ambient", "lofi", "electronic", "cinematic", "jazz", "classical"] as const;
const EXAMPLE_KEYS = ["example1", "example2", "example3"] as const;
const FAQ_KEYS = ["1", "2", "3", "4"] as const;

export default async function LandingPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const m: Messages = await getMessages(locale);
  const t = (key: string) => lookup(m, key);
  const base = `/${locale}`;

  return (
    <div className="mx-auto max-w-6xl space-y-20 px-4 pb-10 pt-14 sm:pt-20">
      <section className="grid items-center gap-10 md:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-6">
          <h1 className="text-4xl font-semibold leading-[1.05] tracking-tight text-white sm:text-6xl">
            {t("landing.heroTitle")}
          </h1>
          <p className="max-w-xl text-lg text-mist">{t("landing.heroSubtitle")}</p>
          <div className="flex flex-wrap gap-3">
            <ButtonLink href={`${base}/register`}>{t("landing.ctaStart")}</ButtonLink>
            <ButtonLink href={`${base}/login`} variant="secondary">
              {t("landing.ctaLogin")}
            </ButtonLink>
          </div>
        </div>
        <div aria-hidden className="relative hidden aspect-square rounded-[2.5rem] border border-line bg-gradient-to-br from-plum/70 via-violet-deep/50 to-night p-10 md:block">
          <div className="flex h-full items-end gap-2">
            {Array.from({ length: 24 }).map((_, i) => (
              <span
                key={i}
                className="w-full rounded-full bg-lavender/80"
                style={{ height: `${28 + ((i * 37) % 60)}%`, opacity: 0.35 + ((i * 13) % 60) / 100 }}
              />
            ))}
          </div>
        </div>
      </section>

      <section aria-labelledby="styles-title" className="space-y-6">
        <div>
          <h2 id="styles-title" className="text-2xl font-semibold text-white">{t("landing.stylesTitle")}</h2>
          <p className="text-mist">{t("landing.stylesSubtitle")}</p>
        </div>
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {STYLE_KEYS.map((k) => (
            <li key={k}>
              <Card className="h-full">
                <h3 className="font-medium text-white">{t(`landing.style_${k}`)}</h3>
                <p className="mt-1 text-sm text-mist">{t(`landing.style_${k}_desc`)}</p>
              </Card>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="examples-title" className="space-y-6">
        <div>
          <h2 id="examples-title" className="text-2xl font-semibold text-white">{t("landing.examplesTitle")}</h2>
          <p className="text-mist">{t("landing.examplesSubtitle")}</p>
        </div>
        <ul className="grid gap-4 md:grid-cols-3">
          {EXAMPLE_KEYS.map((k) => (
            <li key={k}>
              <blockquote className="h-full rounded-3xl border border-line bg-surface/50 p-5 text-sm leading-relaxed text-lavender-soft">
                “{t(`landing.${k}`)}”
              </blockquote>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="pricing-title" className="grid gap-6 md:grid-cols-[1fr_1.2fr]">
        <div className="space-y-3">
          <h2 id="pricing-title" className="text-2xl font-semibold text-white">{t("landing.pricingTitle")}</h2>
          <p className="text-mist">{t("landing.pricingSubtitle")}</p>
          <p className="text-sm text-mist/80">{t("landing.pricingNote")}</p>
        </div>
        <Card>
          <h3 className="font-medium text-white">{t("billing.packages")}</h3>
          <p className="mt-2 text-sm text-mist">{t("billing.noPackages")}</p>
          <Link href={`${base}/billing`} className="mt-4 inline-block text-sm text-lavender hover:underline">
            {t("dashboard.buy")} →
          </Link>
        </Card>
      </section>

      <section aria-labelledby="faq-title" className="space-y-6">
        <h2 id="faq-title" className="text-2xl font-semibold text-white">{t("landing.faqTitle")}</h2>
        <dl className="grid gap-4 md:grid-cols-2">
          {FAQ_KEYS.map((n) => (
            <div key={n} className="rounded-3xl border border-line bg-surface/50 p-5">
              <dt className="font-medium text-white">{t(`landing.faq_q${n}`)}</dt>
              <dd className="mt-2 text-sm text-mist">{t(`landing.faq_a${n}`)}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
