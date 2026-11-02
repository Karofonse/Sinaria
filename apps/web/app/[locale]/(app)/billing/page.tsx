"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/components/i18n-provider";
import { Button, Card, Notice, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { formatCop } from "@/lib/format";
import type { CreditPackage } from "@/lib/types";

export default function BillingPage() {
  const { t, locale } = useI18n();
  const [packages, setPackages] = useState<CreditPackage[] | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    api<CreditPackage[]>("/v1/catalog/packages").then(setPackages).catch(() => setPackages([]));
  }, []);

  async function checkout() {
    setNotice(null);
    try {
      await api("/v1/billing/checkout", { method: "POST" });
    } catch (err) {
      setNotice(err instanceof ApiError && err.status === 503 ? t("billing.paymentsDisabled") : t("common.errorGeneric"));
    }
  }

  return (
    <>
      <PageHeader title={t("billing.title")} subtitle={t("billing.subtitle")} />
      {notice ? <div className="mb-6"><Notice tone="warning">{notice}</Notice></div> : null}
      <div className="grid gap-6 md:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <h2 className="font-medium text-white">{t("billing.packages")}</h2>
          {packages === null ? (
            <div className="mt-4"><Spinner label={t("common.loading")} /></div>
          ) : packages.length === 0 ? (
            <p className="mt-3 text-sm text-mist">{t("billing.noPackages")}</p>
          ) : (
            <ul className="mt-4 grid gap-4 sm:grid-cols-2">
              {packages.map((p) => (
                <li key={p.code} className="rounded-2xl border border-line bg-midnight/50 p-5">
                  <p className="font-medium text-white">{p.name}</p>
                  <p className="mt-1 text-sm text-mist">{t("billing.credits", { credits: p.credits })}</p>
                  <p className="mt-3 text-lg text-lavender-soft">{formatCop(p.price_cop_cents, locale)}</p>
                  <Button className="mt-4 w-full" onClick={checkout}>{t("billing.checkout")}</Button>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <h2 className="font-medium text-white">{t("billing.invoicesTitle")}</h2>
          <p className="mt-3 text-sm text-mist">{t("billing.invoicesBody")}</p>
        </Card>
      </div>
    </>
  );
}
