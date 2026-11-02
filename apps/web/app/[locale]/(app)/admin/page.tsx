"use client";

import { useEffect, useState } from "react";
import { useI18n } from "@/components/i18n-provider";
import { Button, Card, inputClass, Notice, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { useSession } from "@/lib/session";
import type { AdminUser } from "@/lib/types";

type Metrics = {
  jobs_by_status: Record<string, number>;
  credits_issued: number;
  credits_consumed: number;
  credits_reserved_now: number;
  today: { jobs: number; credits_reserved: number };
  usage_by_provider: { provider: string; model_key: string; completed: number; failed: number; credits_charged: number; estimated_cost_micros: number }[];
  failures_by_code: { error_code: string | null; count: number }[];
};

export default function AdminPage() {
  const { t, locale } = useI18n();
  const session = useSession();
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const isAdmin = session.status === "authenticated" && session.me.roles.includes("admin");

  useEffect(() => {
    if (!isAdmin) return;
    api<Metrics>("/v1/admin/metrics").then(setMetrics).catch((e) => setError(e instanceof ApiError ? t("admin.forbidden") : t("common.networkError")));
    api<AdminUser[]>("/v1/admin/users?limit=50").then(setUsers).catch(() => setUsers([]));
  }, [isAdmin, t]);

  async function setStatus(user: AdminUser, action: "suspend" | "activate") {
    try {
      const updated = await api<AdminUser>(`/v1/admin/users/${user.id}/${action}`, {
        json: { reason: reason.trim() || t("admin.reasonDefault") },
      });
      setUsers((rows) => rows?.map((r) => (r.id === updated.id ? updated : r)) ?? null);
    } catch {
      setError(t("common.errorGeneric"));
    }
  }

  if (session.status !== "authenticated") return <Spinner label={t("common.loading")} />;
  if (!isAdmin) return <Notice tone="error">{t("admin.forbidden")}</Notice>;

  return (
    <>
      <PageHeader title={t("admin.title")} />
      {error ? <div className="mb-6"><Notice tone="error">{error}</Notice></div> : null}

      <section aria-labelledby="metrics-title" className="mb-8">
        <h2 id="metrics-title" className="mb-4 text-lg font-medium text-white">{t("admin.metrics")}</h2>
        {!metrics ? <Spinner label={t("common.loading")} /> : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card><p className="text-xs text-mist">{t("admin.creditsIssued")}</p><p className="mt-1 text-2xl tabular-nums text-white">{metrics.credits_issued}</p></Card>
            <Card><p className="text-xs text-mist">{t("admin.creditsConsumed")}</p><p className="mt-1 text-2xl tabular-nums text-white">{metrics.credits_consumed}</p></Card>
            <Card><p className="text-xs text-mist">{t("admin.reservedNow")}</p><p className="mt-1 text-2xl tabular-nums text-white">{metrics.credits_reserved_now}</p></Card>
            <Card><p className="text-xs text-mist">{t("admin.todayJobs")}</p><p className="mt-1 text-2xl tabular-nums text-white">{metrics.today.jobs}</p></Card>
            <Card className="sm:col-span-2 lg:col-span-2">
              <h3 className="mb-2 text-sm font-medium text-white">{t("admin.usageByProvider")}</h3>
              <ul className="space-y-1 text-sm text-mist">
                {metrics.usage_by_provider.length === 0 ? <li>—</li> : metrics.usage_by_provider.map((u) => (
                  <li key={`${u.provider}-${u.model_key}`}>{u.provider} · {u.model_key}: ✓ {u.completed} · ✕ {u.failed} · {u.credits_charged} cr</li>
                ))}
              </ul>
            </Card>
            <Card className="sm:col-span-2 lg:col-span-2">
              <h3 className="mb-2 text-sm font-medium text-white">{t("admin.failures")}</h3>
              <ul className="space-y-1 text-sm text-mist">
                {metrics.failures_by_code.length === 0 ? <li>—</li> : metrics.failures_by_code.map((f) => (
                  <li key={f.error_code ?? "none"}>{f.error_code ?? "unknown"}: {f.count}</li>
                ))}
              </ul>
            </Card>
          </div>
        )}
      </section>

      <section aria-labelledby="users-title">
        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
          <h2 id="users-title" className="text-lg font-medium text-white">{t("admin.users")}</h2>
          <div className="w-full max-w-xs">
            <label htmlFor="reason" className="mb-1 block text-xs text-mist">{t("admin.reasonLabel")}</label>
            <input id="reason" className={inputClass} value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t("admin.reasonDefault")} />
          </div>
        </div>
        {!users ? <Spinner label={t("common.loading")} /> : (
          <div className="overflow-x-auto rounded-3xl border border-line">
            <table className="w-full text-sm">
              <thead className="bg-surface-2/60 text-left text-mist">
                <tr>
                  <th scope="col" className="px-4 py-3 font-normal">{t("auth.email")}</th>
                  <th scope="col" className="px-4 py-3 font-normal">{t("profile.name")}</th>
                  <th scope="col" className="px-4 py-3 font-normal">Status</th>
                  <th scope="col" className="px-4 py-3 font-normal"><span className="sr-only">Acciones</span></th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-t border-line">
                    <td className="px-4 py-3 text-white">{u.email}</td>
                    <td className="px-4 py-3 text-lavender-soft">{u.display_name}</td>
                    <td className="px-4 py-3 text-mist">{u.status === "active" ? t("admin.statusActive") : t("admin.statusSuspended")} · {formatDate(u.created_at, locale)}</td>
                    <td className="px-4 py-3 text-right">
                      {u.status === "active" ? (
                        <Button variant="danger" onClick={() => setStatus(u, "suspend")}>{t("admin.suspend")}</Button>
                      ) : (
                        <Button variant="secondary" onClick={() => setStatus(u, "activate")}>{t("admin.activate")}</Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
