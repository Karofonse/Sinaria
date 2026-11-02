"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { useI18n } from "@/components/i18n-provider";
import { Button, Card, Field, inputClass, Notice } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { emailSchema, nameSchema, passwordSchema } from "@/lib/validation";

type FieldErrors = { email?: string; password?: string; name?: string };

export default function RegisterPage() {
  const { t, locale } = useI18n();
  const router = useRouter();
  const [form, setForm] = useState({ email: "", password: "", name: "" });
  const [errors, setErrors] = useState<FieldErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function update(field: keyof typeof form, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setServerError(null);
    const email = emailSchema.safeParse(form.email);
    const password = passwordSchema.safeParse(form.password);
    const name = nameSchema.safeParse(form.name);
    const next: FieldErrors = {};
    if (!email.success) next.email = t(email.error.issues[0].message);
    if (!password.success) next.password = t(password.error.issues[0].message);
    if (!name.success) next.name = t(name.error.issues[0].message);
    setErrors(next);
    if (Object.keys(next).length) return;

    setSubmitting(true);
    try {
      await api("/v1/auth/register", {
        json: { email: email.success ? email.data : form.email, password: form.password, display_name: form.name, locale },
      });
      router.replace(`/${locale}/studio`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setServerError(t("auth.emailTaken"));
      else if (err instanceof ApiError && err.status === 429) setServerError(t("auth.rateLimited"));
      else if (err instanceof ApiError && err.status === 422) setServerError(t("auth.passwordShort"));
      else setServerError(t("common.networkError"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto grid min-h-[70dvh] max-w-md place-items-center px-4 py-12">
      <Card className="w-full">
        <h1 className="text-2xl font-semibold text-white">{t("auth.registerTitle")}</h1>
        <p className="mb-6 mt-1 text-mist">{t("auth.registerSubtitle")}</p>
        <form onSubmit={onSubmit} noValidate className="space-y-5">
          {serverError ? <Notice tone="error">{serverError}</Notice> : null}
          <Field id="name" label={t("auth.displayName")} error={errors.name}>
            <input id="name" className={inputClass} autoComplete="name" value={form.name} onChange={(e) => update("name", e.target.value)} aria-invalid={!!errors.name} />
          </Field>
          <Field id="email" label={t("auth.email")} error={errors.email}>
            <input id="email" type="email" className={inputClass} autoComplete="email" value={form.email} onChange={(e) => update("email", e.target.value)} aria-invalid={!!errors.email} />
          </Field>
          <Field id="password" label={t("auth.password")} hint={t("auth.passwordHint")} error={errors.password}>
            <input id="password" type="password" className={inputClass} autoComplete="new-password" value={form.password} onChange={(e) => update("password", e.target.value)} aria-invalid={!!errors.password} />
          </Field>
          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? t("auth.submitting") : t("auth.submitRegister")}
          </Button>
        </form>
        <p className="mt-6 text-sm text-mist">
          {t("auth.haveAccount")}{" "}
          <Link href={`/${locale}/login`} className="text-lavender hover:underline">
            {t("nav.login")}
          </Link>
        </p>
      </Card>
    </div>
  );
}
