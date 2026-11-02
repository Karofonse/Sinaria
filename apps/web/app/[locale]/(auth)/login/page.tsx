"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { useI18n } from "@/components/i18n-provider";
import { Button, Card, Field, inputClass, Notice } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { emailSchema, passwordSchema } from "@/lib/validation";

export default function LoginPage() {
  const { t, locale } = useI18n();
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setServerError(null);
    const emailResult = emailSchema.safeParse(email);
    const passwordResult = passwordSchema.safeParse(password);
    const next: { email?: string; password?: string } = {};
    if (!emailResult.success) next.email = t(emailResult.error.issues[0].message);
    if (!passwordResult.success) next.password = t(passwordResult.error.issues[0].message);
    setErrors(next);
    if (Object.keys(next).length) return;

    setSubmitting(true);
    try {
      await api("/v1/auth/login", { json: { email: emailResult.data, password } });
      const next = params.get("next");
      router.replace(next && next.startsWith(`/${locale}/`) ? next : `/${locale}/studio`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setServerError(t("auth.invalidCredentials"));
      else if (err instanceof ApiError && err.status === 403) setServerError(t("auth.accountSuspended"));
      else if (err instanceof ApiError && err.status === 429) setServerError(t("auth.rateLimited"));
      else setServerError(t("common.networkError"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto grid min-h-[70dvh] max-w-md place-items-center px-4 py-12">
      <Card className="w-full">
        <h1 className="text-2xl font-semibold text-white">{t("auth.loginTitle")}</h1>
        <p className="mb-6 mt-1 text-mist">{t("auth.loginSubtitle")}</p>
        <form onSubmit={onSubmit} noValidate className="space-y-5">
          {serverError ? <Notice tone="error">{serverError}</Notice> : null}
          <Field id="email" label={t("auth.email")} error={errors.email}>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              className={inputClass}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              aria-invalid={!!errors.email}
              aria-describedby={errors.email ? "email-error" : undefined}
            />
          </Field>
          <Field id="password" label={t("auth.password")} error={errors.password}>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              className={inputClass}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-invalid={!!errors.password}
              aria-describedby={errors.password ? "password-error" : undefined}
            />
          </Field>
          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? t("auth.submitting") : t("auth.submitLogin")}
          </Button>
        </form>
        <p className="mt-6 text-sm text-mist">
          {t("auth.noAccount")}{" "}
          <Link href={`/${locale}/register`} className="text-lavender hover:underline">
            {t("nav.register")}
          </Link>
        </p>
        <p className="mt-2 text-xs text-mist/80">{t("auth.forgotPending")}</p>
      </Card>
    </div>
  );
}
