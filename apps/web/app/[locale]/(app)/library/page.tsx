"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useI18n } from "@/components/i18n-provider";
import { Button, ButtonLink, Card, inputClass, Notice, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatDuration } from "@/lib/format";
import type { Track } from "@/lib/types";

export default function LibraryPage() {
  const { t, locale } = useI18n();
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [tracks, setTracks] = useState<Track[] | null>(null);
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [renaming, setRenaming] = useState<{ id: string; title: string } | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query.trim()), 300);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    let cancelled = false;
    setTracks(null);
    api<Track[]>(`/v1/tracks?limit=50${debounced ? `&q=${encodeURIComponent(debounced)}` : ""}`)
      .then((rows) => !cancelled && setTracks(rows))
      .catch(() => !cancelled && setTracks([]));
    return () => {
      cancelled = true;
    };
  }, [debounced]);

  async function rename(e: React.FormEvent) {
    e.preventDefault();
    if (!renaming) return;
    try {
      const updated = await api<Track>(`/v1/tracks/${renaming.id}`, { method: "PATCH", json: { title: renaming.title } });
      setTracks((rows) => rows?.map((r) => (r.id === updated.id ? updated : r)) ?? null);
      setMessage({ tone: "success", text: t("library.renamed") });
    } catch (err) {
      setMessage({ tone: "error", text: err instanceof ApiError ? t("library.notFound") : t("common.networkError") });
    } finally {
      setRenaming(null);
    }
  }

  async function remove(id: string) {
    if (!window.confirm(t("common.confirmDelete"))) return;
    try {
      await api<void>(`/v1/tracks/${id}`, { method: "DELETE" });
      setTracks((rows) => rows?.filter((r) => r.id !== id) ?? null);
      setMessage({ tone: "success", text: t("library.deleted") });
    } catch {
      setMessage({ tone: "error", text: t("common.networkError") });
    }
  }

  return (
    <>
      <PageHeader title={t("library.title")} subtitle={t("library.subtitle")} />
      <div className="mb-6">
        <label htmlFor="search" className="sr-only">{t("library.search")}</label>
        <input id="search" type="search" placeholder={t("library.search")} className={inputClass} value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>
      {message ? <div className="mb-4"><Notice tone={message.tone}>{message.text}</Notice></div> : null}

      {tracks === null ? (
        <Spinner label={t("common.loading")} />
      ) : tracks.length === 0 ? (
        <Card className="text-center">
          <h2 className="text-lg font-medium text-white">{debounced ? t("common.empty") : t("library.emptyTitle")}</h2>
          {!debounced ? (
            <>
              <p className="mx-auto mt-1 max-w-sm text-mist">{t("library.emptyBody")}</p>
              <div className="mt-5"><ButtonLink href={`/${locale}/studio`}>{t("library.emptyCta")}</ButtonLink></div>
            </>
          ) : null}
        </Card>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2">
          {tracks.map((track) => (
            <li key={track.id}>
              <Card className="flex h-full flex-col gap-4">
                {renaming?.id === track.id ? (
                  <form onSubmit={rename} className="flex gap-2">
                    <label htmlFor={`rename-${track.id}`} className="sr-only">{t("library.renameLabel")}</label>
                    <input id={`rename-${track.id}`} className={inputClass} value={renaming.title} maxLength={200} onChange={(e) => setRenaming({ id: track.id, title: e.target.value })} autoFocus />
                    <Button type="submit" variant="secondary">{t("common.save")}</Button>
                    <Button type="button" variant="ghost" onClick={() => setRenaming(null)}>{t("common.cancel")}</Button>
                  </form>
                ) : (
                  <div className="min-w-0">
                    <Link href={`/${locale}/library/${track.id}`} className="block truncate font-medium text-white hover:text-lavender">
                      {track.title}
                    </Link>
                    <p className="mt-1 text-xs text-mist">
                      {t("library.model")}: {track.model_key} · {formatDuration(track.duration_seconds)} · {formatDate(track.created_at, locale)}
                    </p>
                  </div>
                )}
                <div className="mt-auto flex flex-wrap gap-2">
                  <ButtonLink href={`/${locale}/library/${track.id}`} variant="secondary">{t("library.open")}</ButtonLink>
                  <Button variant="ghost" onClick={() => setRenaming({ id: track.id, title: track.title })}>{t("common.rename")}</Button>
                  <Button variant="danger" onClick={() => remove(track.id)}>{t("common.delete")}</Button>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
