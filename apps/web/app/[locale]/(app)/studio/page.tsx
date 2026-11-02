"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { AudioPlayer } from "@/components/audio-player";
import { useI18n } from "@/components/i18n-provider";
import { Button, Card, Field, inputClass, Notice, PageHeader, Spinner, StatusBadge } from "@/components/ui";
import { api, ApiError, newIdempotencyKey } from "@/lib/api";
import { downloadTrack } from "@/lib/tracks";
import type { Balance, Generation, ProviderModel, Track } from "@/lib/types";
import { GENRES, INSTRUMENTS, MOODS, buildGenerationSchema, isTerminal, toGenerationPayload } from "@/lib/validation";

const POLL_MS = 2500;

type FormValues = {
  prompt: string;
  negativePrompt: string;
  genre: string;
  mood: string;
  instruments: string[];
  durationSeconds: number;
  seed: string;
};

const INITIAL: FormValues = {
  prompt: "",
  negativePrompt: "",
  genre: "",
  mood: "",
  instruments: [],
  durationSeconds: 30,
  seed: "",
};

export default function StudioPage() {
  const { t, locale } = useI18n();
  const [models, setModels] = useState<ProviderModel[] | null>(null);
  const [modelKey, setModelKey] = useState<string>("");
  const [balance, setBalance] = useState<Balance | null>(null);
  const [values, setValues] = useState<FormValues>(INITIAL);
  const [errors, setErrors] = useState<Partial<Record<keyof FormValues, string>>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [job, setJob] = useState<Generation | null>(null);
  const [track, setTrack] = useState<Track | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  // Clave de idempotencia reutilizada mientras el payload no cambie: un doble clic o un reintento
  // de red devuelven la misma generación en lugar de crear otra y cobrarla.
  const idemRef = useRef<{ key: string; fingerprint: string } | null>(null);

  const model = models?.find((m) => m.model_key === modelKey) ?? null;

  useEffect(() => {
    api<ProviderModel[]>("/v1/catalog/models")
      .then((list) => {
        setModels(list);
        if (list[0]) {
          setModelKey(list[0].model_key);
          setValues((v) => ({ ...v, durationSeconds: Math.min(30, list[0].max_duration_s) }));
        }
      })
      .catch(() => setModels([]));
    api<Balance>("/v1/wallet").then(setBalance).catch(() => undefined);
  }, []);

  // Sondeo del estado hasta un estado terminal. Se cancela al desmontar o al cambiar de trabajo.
  useEffect(() => {
    if (!job || isTerminal(job.status)) return;
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const next = await api<Generation>(`/v1/generations/${job.id}`);
        if (!cancelled) setJob(next);
      } catch {
        if (!cancelled) setSubmitError(t("common.networkError"));
      }
    }, POLL_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [job, t]);

  // Cuando la generación se completa, cargamos la pista para el reproductor.
  useEffect(() => {
    if (job?.status !== "completed" || !job.track_id) return;
    api<Track>(`/v1/tracks/${job.track_id}`)
      .then(setTrack)
      .catch(() => setTrack(null));
    api<Balance>("/v1/wallet").then(setBalance).catch(() => undefined);
  }, [job]);

  function update<K extends keyof FormValues>(key: K, value: FormValues[K]) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  function toggleInstrument(name: string) {
    setValues((v) => ({
      ...v,
      instruments: v.instruments.includes(name) ? v.instruments.filter((i) => i !== name) : [...v.instruments, name],
    }));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!model) return;
    setSubmitError(null);
    setTrack(null);
    setDownloadError(null);

    const schema = buildGenerationSchema(model);
    const parsed = schema.safeParse(values);
    if (!parsed.success) {
      const next: Partial<Record<keyof FormValues, string>> = {};
      for (const issue of parsed.error.issues) {
        const field = String(issue.path[0]) as keyof FormValues;
        next[field] = t(issue.message);
      }
      setErrors(next);
      return;
    }
    setErrors({});

    const payload = toGenerationPayload(model.model_key, values, model);
    const fingerprint = JSON.stringify(payload);
    if (!idemRef.current || idemRef.current.fingerprint !== fingerprint) {
      idemRef.current = { key: newIdempotencyKey(), fingerprint };
    }

    setSubmitting(true);
    try {
      const created = await api<Generation>("/v1/generations", {
        json: payload,
        idempotencyKey: idemRef.current.key,
      });
      setJob(created);
      api<Balance>("/v1/wallet").then(setBalance).catch(() => undefined);
    } catch (err) {
      if (err instanceof ApiError) {
        const map: Record<string, string> = {
          insufficient_credits: t("studio.insufficientCredits"),
          budget_exceeded: t("studio.budgetExceeded"),
          conflict: t("studio.conflict"),
          not_found: t("studio.modelUnavailable"),
          invalid_request: t("studio.durationInvalid"),
        };
        setSubmitError(map[err.code] ?? t("common.errorGeneric"));
      } else {
        setSubmitError(t("common.networkError"));
      }
    } finally {
      setSubmitting(false);
    }
  }

  function startNew() {
    setJob(null);
    setTrack(null);
    setDownloadError(null);
    idemRef.current = null;
  }

  const busy = submitting || (job !== null && !isTerminal(job.status));

  return (
    <>
      <PageHeader title={t("studio.title")} subtitle={t("studio.subtitle")} />
      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <Card>
          {models === null ? (
            <Spinner label={t("common.loading")} />
          ) : models.length === 0 ? (
            <Notice tone="warning">{t("studio.noModels")}</Notice>
          ) : (
            <form onSubmit={onSubmit} noValidate className="space-y-6">
              {submitError ? <Notice tone="error">{submitError}</Notice> : null}

              <Field id="model" label={t("studio.model")}>
                <select id="model" className={inputClass} value={modelKey} onChange={(e) => setModelKey(e.target.value)} disabled={busy}>
                  {models.map((m) => (
                    <option key={m.model_key} value={m.model_key}>
                      {m.display_name} · {m.credits_per_generation} cr
                    </option>
                  ))}
                </select>
              </Field>

              <Field id="prompt" label={t("studio.prompt")} error={errors.prompt} hint={`${values.prompt.length}/2000`}>
                <textarea
                  id="prompt"
                  rows={4}
                  className={inputClass}
                  placeholder={t("studio.promptPlaceholder")}
                  value={values.prompt}
                  onChange={(e) => update("prompt", e.target.value)}
                  disabled={busy}
                  aria-invalid={!!errors.prompt}
                  maxLength={2000}
                />
              </Field>

              {model?.supports_negative_prompt ? (
                <Field id="negativePrompt" label={t("studio.negativePrompt")} error={errors.negativePrompt}>
                  <input id="negativePrompt" className={inputClass} placeholder={t("studio.negativePlaceholder")} value={values.negativePrompt} onChange={(e) => update("negativePrompt", e.target.value)} disabled={busy} />
                </Field>
              ) : null}

              <div className="grid gap-5 sm:grid-cols-2">
                <Field id="genre" label={t("studio.genre")}>
                  <select id="genre" className={inputClass} value={values.genre} onChange={(e) => update("genre", e.target.value)} disabled={busy}>
                    <option value="">—</option>
                    {GENRES.map((g) => (
                      <option key={g} value={g}>{t(`studio.genres.${g}`)}</option>
                    ))}
                  </select>
                </Field>
                <Field id="mood" label={t("studio.mood")}>
                  <select id="mood" className={inputClass} value={values.mood} onChange={(e) => update("mood", e.target.value)} disabled={busy}>
                    <option value="">—</option>
                    {MOODS.map((m) => (
                      <option key={m} value={m}>{t(`studio.moods.${m}`)}</option>
                    ))}
                  </select>
                </Field>
              </div>

              <fieldset className="space-y-2">
                <legend className="text-sm font-medium text-lavender-soft">{t("studio.instruments")}</legend>
                <div className="flex flex-wrap gap-2">
                  {INSTRUMENTS.map((inst) => {
                    const on = values.instruments.includes(inst);
                    return (
                      <label
                        key={inst}
                        className={`cursor-pointer select-none rounded-full px-3.5 py-1.5 text-sm ring-1 transition-colors ${on ? "bg-lavender text-midnight ring-lavender" : "text-mist ring-line hover:text-white"}`}
                      >
                        <input type="checkbox" className="sr-only" checked={on} onChange={() => toggleInstrument(inst)} disabled={busy} />
                        {t(`studio.instrumentOptions.${inst}`)}
                      </label>
                    );
                  })}
                </div>
              </fieldset>

              <div className="grid gap-5 sm:grid-cols-2">
                <Field
                  id="duration"
                  label={t("studio.duration")}
                  error={errors.durationSeconds}
                  hint={model ? t("studio.durationRange", { min: model.min_duration_s, max: model.max_duration_s }) : undefined}
                >
                  <input
                    id="duration"
                    type="number"
                    inputMode="numeric"
                    min={model?.min_duration_s}
                    max={model?.max_duration_s}
                    className={inputClass}
                    value={values.durationSeconds}
                    onChange={(e) => update("durationSeconds", Number(e.target.value))}
                    disabled={busy}
                    aria-invalid={!!errors.durationSeconds}
                  />
                </Field>
                {model?.supports_seed ? (
                  <Field id="seed" label={t("studio.seed")} error={errors.seed} hint={t("studio.seedHint")}>
                    <input id="seed" inputMode="numeric" className={inputClass} value={values.seed} onChange={(e) => update("seed", e.target.value.trim())} disabled={busy} aria-invalid={!!errors.seed} />
                  </Field>
                ) : null}
              </div>

              <p className="text-xs text-mist">{t("studio.instrumentalOnly")}</p>

              <div className="flex flex-wrap items-center justify-between gap-4 border-t border-line pt-5">
                <div className="text-sm text-mist">
                  {model ? <p>{t("studio.cost", { credits: model.credits_per_generation })}</p> : null}
                  {balance ? <p>{t("studio.balance", { credits: balance.available_credits })}</p> : null}
                </div>
                <Button type="submit" disabled={busy || !model}>
                  {submitting ? t("studio.submitting") : t("studio.submit")}
                </Button>
              </div>
            </form>
          )}
        </Card>

        <Card className="h-fit">
          <h2 className="mb-4 font-medium text-white">{t("studio.statusTitle")}</h2>
          {!job ? (
            <p className="text-sm text-mist">{t("studio.subtitle")}</p>
          ) : (
            <div className="space-y-4" aria-live="polite">
              <StatusBadge status={job.status} label={t(`studio.status_${job.status}`)} />
              <p className="line-clamp-3 text-sm text-lavender-soft">{job.prompt}</p>
              {job.status === "pending" || job.status === "processing" ? (
                <Spinner label={t(`studio.status_${job.status}`)} />
              ) : null}
              {job.status === "failed" ? (
                <Notice tone="error">
                  <p>{job.error_message ?? t("common.errorGeneric")}</p>
                  <p className="mt-1 text-xs opacity-80">{t("studio.failedHint")}</p>
                </Notice>
              ) : null}
              {job.status === "completed" && track ? (
                <div className="space-y-3">
                  <p className="text-sm font-medium text-white">{t("studio.result")}</p>
                  <AudioPlayer track={track} />
                  {downloadError ? <Notice tone="error">{downloadError}</Notice> : null}
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="secondary"
                      onClick={() =>
                        downloadTrack(track.id, `${track.title}.wav`).catch(() => setDownloadError(t("common.errorGeneric")))
                      }
                    >
                      {t("studio.download")}
                    </Button>
                  </div>
                </div>
              ) : null}
              {job.status === "completed" || job.status === "failed" ? (
                <div className="flex flex-wrap gap-2 pt-2">
                  {job.status === "completed" && track ? (
                    <Link href={`/${locale}/library/${track.id}`} className="rounded-full bg-surface-2 px-4 py-2 text-sm text-lavender ring-1 ring-line hover:bg-plum">
                      {t("studio.openTrack")}
                    </Link>
                  ) : null}
                  <Button variant="ghost" onClick={startNew}>
                    {t("studio.newGeneration")}
                  </Button>
                </div>
              ) : null}
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
