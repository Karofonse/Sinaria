"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AudioPlayer } from "@/components/audio-player";
import { useI18n } from "@/components/i18n-provider";
import { Button, Card, inputClass, Notice, PageHeader, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { formatBytes, formatDate, formatDuration } from "@/lib/format";
import { downloadTrack } from "@/lib/tracks";
import type { Track } from "@/lib/types";

export default function TrackDetailPage() {
  const { t, locale } = useI18n();
  const router = useRouter();
  const { id } = useParams<{ id: string }>();
  const [track, setTrack] = useState<Track | null | "missing">(null);
  const [title, setTitle] = useState("");
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    api<Track>(`/v1/tracks/${id}`)
      .then((row) => {
        if (cancelled) return;
        setTrack(row);
        setTitle(row.title);
      })
      .catch((err) => {
        if (cancelled) return;
        setTrack(err instanceof ApiError && err.status === 404 ? "missing" : "missing");
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  async function rename(e: React.FormEvent) {
    e.preventDefault();
    try {
      const updated = await api<Track>(`/v1/tracks/${id}`, { method: "PATCH", json: { title } });
      setTrack(updated);
      setNotice({ tone: "success", text: t("library.renamed") });
    } catch {
      setNotice({ tone: "error", text: t("common.errorGeneric") });
    }
  }

  async function remove() {
    if (!window.confirm(t("common.confirmDelete"))) return;
    try {
      await api<void>(`/v1/tracks/${id}`, { method: "DELETE" });
      router.push(`/${locale}/library`);
    } catch {
      setNotice({ tone: "error", text: t("common.errorGeneric") });
    }
  }

  if (track === null) return <Spinner label={t("common.loading")} />;
  if (track === "missing") {
    return (
      <Card>
        <Notice tone="error">{t("library.notFound")}</Notice>
        <Link href={`/${locale}/library`} className="mt-4 inline-block text-sm text-lavender hover:underline">
          ← {t("common.back")}
        </Link>
      </Card>
    );
  }

  const meta: [string, string][] = [
    [t("library.model"), track.model_key],
    [t("library.provider"), track.provider],
    [t("library.duration"), formatDuration(track.duration_seconds)],
    [t("library.size"), formatBytes(track.size_bytes)],
    [t("library.created"), formatDate(track.created_at, locale)],
  ];

  return (
    <>
      <PageHeader title={track.title} />
      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-6">
          <AudioPlayer track={track} />
          <Card>
            <h2 className="mb-4 font-medium text-white">{t("library.metadata")}</h2>
            <dl className="grid gap-4 text-sm sm:grid-cols-2">
              {meta.map(([label, value]) => (
                <div key={label}>
                  <dt className="text-mist">{label}</dt>
                  <dd className="text-white">{value}</dd>
                </div>
              ))}
            </dl>
          </Card>
        </div>
        <div className="space-y-6">
          <Card>
            <form onSubmit={rename} className="space-y-3">
              <label htmlFor="title" className="block text-sm font-medium text-lavender-soft">{t("library.renameLabel")}</label>
              <input id="title" className={inputClass} maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />
              <Button type="submit" variant="secondary" className="w-full">{t("common.rename")}</Button>
            </form>
          </Card>
          <Card className="space-y-3">
            <Button className="w-full" onClick={() => downloadTrack(track.id, `${track.title}.wav`).catch(() => setNotice({ tone: "error", text: t("common.errorGeneric") }))}>
              {t("library.download")}
            </Button>
            <Button variant="danger" className="w-full" onClick={remove}>{t("common.delete")}</Button>
          </Card>
          {notice ? <Notice tone={notice.tone}>{notice.text}</Notice> : null}
        </div>
      </div>
    </>
  );
}
