"use client";

import { useEffect, useRef, useState } from "react";
import { useI18n } from "@/components/i18n-provider";
import { api } from "@/lib/api";
import { formatDuration } from "@/lib/format";
import type { Track } from "@/lib/types";

/** Reproductor sobre URL firmada de corta duración. La URL se pide justo antes de reproducir. */
export function AudioPlayer({ track }: { track: Pick<Track, "id" | "title" | "duration_seconds"> }) {
  const { t } = useI18n();
  const audioRef = useRef<HTMLAudioElement>(null);
  const [src, setSrc] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(track.duration_seconds);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api<{ url: string }>(`/v1/tracks/${track.id}/download-url`)
      .then((r) => !cancelled && setSrc(r.url))
      .catch(() => !cancelled && setError(t("library.playerUnavailable")));
    return () => {
      cancelled = true;
    };
  }, [track.id, t]);

  function toggle() {
    const el = audioRef.current;
    if (!el || !src) return;
    if (el.paused) void el.play();
    else el.pause();
  }

  const progress = duration > 0 ? (current / duration) * 100 : 0;

  return (
    <div className="space-y-3 rounded-2xl border border-line bg-midnight/50 p-4">
      <audio
        ref={audioRef}
        src={src ?? undefined}
        preload="metadata"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
        onTimeUpdate={(e) => setCurrent(e.currentTarget.currentTime)}
        onLoadedMetadata={(e) => Number.isFinite(e.currentTarget.duration) && setDuration(e.currentTarget.duration)}
        onError={() => setError(t("library.playerUnavailable"))}
      />
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={toggle}
          disabled={!src || !!error}
          aria-label={playing ? "Pause" : "Play"}
          className="grid size-12 shrink-0 place-items-center rounded-full bg-lavender text-midnight shadow-[0_10px_30px_-10px_rgb(201_184_255/0.7)] hover:bg-lavender-soft disabled:opacity-40"
        >
          <span aria-hidden className="text-lg">{playing ? "❚❚" : "▶"}</span>
        </button>
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium text-white">{track.title}</p>
          <div className="mt-2 flex items-center gap-3 text-xs text-mist">
            <span className="tabular-nums">{formatDuration(current)}</span>
            <div className="relative h-1.5 flex-1 rounded-full bg-surface-2">
              <div className="absolute inset-y-0 left-0 rounded-full bg-lavender" style={{ width: `${progress}%` }} />
              <input
                type="range"
                min={0}
                max={Math.max(duration, 0.1)}
                step={0.1}
                value={current}
                aria-label="Seek"
                disabled={!src}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  if (audioRef.current) audioRef.current.currentTime = v;
                  setCurrent(v);
                }}
                className="absolute inset-0 w-full cursor-pointer opacity-0 disabled:cursor-not-allowed"
              />
            </div>
            <span className="tabular-nums">{formatDuration(duration)}</span>
          </div>
        </div>
      </div>
      {error ? <p role="alert" className="text-xs text-danger">{error}</p> : null}
    </div>
  );
}
