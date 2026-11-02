"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useI18n } from "@/components/i18n-provider";
import { ButtonLink, Card, PageHeader, Spinner, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Balance, Generation, LedgerEntry } from "@/lib/types";

export default function DashboardPage() {
  const { t, locale } = useI18n();
  const [balance, setBalance] = useState<Balance | null>(null);
  const [recent, setRecent] = useState<Generation[] | null>(null);
  const [ledger, setLedger] = useState<LedgerEntry[] | null>(null);

  useEffect(() => {
    api<Balance>("/v1/wallet").then(setBalance).catch(() => setBalance({ available_credits: 0, reserved_credits: 0 }));
    api<Generation[]>("/v1/generations?limit=5").then(setRecent).catch(() => setRecent([]));
    api<LedgerEntry[]>("/v1/wallet/transactions?limit=10").then(setLedger).catch(() => setLedger([]));
  }, []);

  return (
    <>
      <PageHeader title={t("dashboard.title")} />
      <div className="grid gap-6 md:grid-cols-3">
        <Card>
          <p className="text-sm text-mist">{t("dashboard.balance")}</p>
          <p className="mt-2 text-4xl font-semibold tabular-nums text-white" aria-live="polite">
            {balance ? balance.available_credits : "—"}
          </p>
          <p className="mt-2 text-xs text-mist">
            {t("dashboard.reserved")}: <span className="tabular-nums">{balance?.reserved_credits ?? "—"}</span>
          </p>
          <div className="mt-5">
            <ButtonLink href={`/${locale}/billing`} variant="secondary">{t("dashboard.buy")}</ButtonLink>
          </div>
        </Card>
        <Card className="md:col-span-2">
          <h2 className="font-medium text-white">{t("dashboard.recent")}</h2>
          {recent === null ? (
            <div className="mt-4"><Spinner label={t("common.loading")} /></div>
          ) : recent.length === 0 ? (
            <p className="mt-3 text-sm text-mist">{t("dashboard.noRecent")}</p>
          ) : (
            <ul className="mt-4 divide-y divide-line">
              {recent.map((g) => (
                <li key={g.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm text-lavender-soft">{g.prompt}</p>
                    <p className="text-xs text-mist">{formatDate(g.created_at, locale)}</p>
                  </div>
                  <StatusBadge status={g.status} label={t(`studio.status_${g.status}`)} />
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card className="md:col-span-2">
          <h2 className="font-medium text-white">{t("dashboard.transactions")}</h2>
          {ledger === null ? (
            <div className="mt-4"><Spinner label={t("common.loading")} /></div>
          ) : ledger.length === 0 ? (
            <p className="mt-3 text-sm text-mist">{t("dashboard.noTransactions")}</p>
          ) : (
            <table className="mt-4 w-full text-sm">
              <thead className="text-left text-mist">
                <tr>
                  <th scope="col" className="pb-2 font-normal">{t("dashboard.transactions")}</th>
                  <th scope="col" className="pb-2 text-right font-normal">{t("dashboard.amount")}</th>
                  <th scope="col" className="pb-2 text-right font-normal">{t("dashboard.date")}</th>
                </tr>
              </thead>
              <tbody>
                {ledger.map((row) => {
                  // Reservas, liberaciones y ajustes se muestran sobre el disponible; los consumos, sobre lo reservado.
                  const delta = row.available_delta !== 0 ? row.available_delta : row.reserved_delta;
                  const kindKey = `dashboard.kind_${row.kind}`;
                  return (
                    <tr key={row.id} className="border-t border-line">
                      <td className="py-2 text-lavender-soft">{t(kindKey)}</td>
                      <td className={`py-2 text-right tabular-nums ${delta < 0 ? "text-danger" : "text-success"}`}>
                        {delta > 0 ? `+${delta}` : delta === 0 ? "0" : delta}
                      </td>
                      <td className="py-2 text-right text-mist">{formatDate(row.created_at, locale)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </Card>
        <Card>
          <h2 className="font-medium text-white">{t("dashboard.plan")}</h2>
          <p className="mt-2 text-white">{t("dashboard.planFree")}</p>
          <p className="mt-2 text-xs text-mist">{t("dashboard.planNote")}</p>
          <Link href={`/${locale}/library`} className="mt-4 inline-block text-sm text-lavender hover:underline">
            {t("nav.library")} →
          </Link>
        </Card>
      </div>
    </>
  );
}
