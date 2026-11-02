import Link from "next/link";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-lavender text-midnight hover:bg-lavender-soft shadow-[0_8px_30px_-12px_rgb(201_184_255/0.6)]",
  secondary: "bg-surface-2 text-lavender-soft ring-1 ring-line hover:bg-plum",
  ghost: "text-lavender hover:bg-surface-2",
  danger: "bg-danger/15 text-danger ring-1 ring-danger/30 hover:bg-danger/25",
};

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${className}`}
    />
  );
}

export function ButtonLink({ href, variant = "primary", children }: { href: string; variant?: Variant; children: ReactNode }) {
  return (
    <Link
      href={href}
      className={`inline-flex items-center justify-center gap-2 rounded-full px-5 py-2.5 text-sm font-medium transition-colors duration-200 ${VARIANTS[variant]}`}
    >
      {children}
    </Link>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-3xl border border-line bg-surface/70 p-5 shadow-[0_20px_60px_-30px_rgb(0_0_0/0.6)] backdrop-blur sm:p-6 ${className}`}>
      {children}
    </section>
  );
}

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className="mb-6 space-y-1">
      <h1 className="text-2xl font-semibold tracking-tight text-white sm:text-3xl">{title}</h1>
      {subtitle ? <p className="text-mist">{subtitle}</p> : null}
    </header>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "error" | "success" | "warning"; children: ReactNode }) {
  const tones = {
    info: "border-line bg-surface-2 text-lavender-soft",
    error: "border-danger/40 bg-danger/10 text-danger",
    success: "border-success/40 bg-success/10 text-success",
    warning: "border-warning/40 bg-warning/10 text-warning",
  };
  return (
    <div role={tone === "error" ? "alert" : "status"} className={`rounded-2xl border px-4 py-3 text-sm ${tones[tone]}`}>
      {children}
    </div>
  );
}

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-mist/15 text-mist",
  processing: "bg-lavender/15 text-lavender",
  completed: "bg-success/15 text-success",
  failed: "bg-danger/15 text-danger",
};

export function StatusBadge({ status, label }: { status: string; label: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_STYLES[status] ?? STATUS_STYLES.pending}`}>
      {status === "processing" ? <span className="size-1.5 animate-pulse rounded-full bg-current" aria-hidden /> : null}
      {label}
    </span>
  );
}

export const inputClass =
  "w-full rounded-2xl border border-line bg-midnight/60 px-4 py-3 text-white placeholder:text-mist/60 focus:border-lavender focus:outline-none focus:ring-2 focus:ring-lavender/30 disabled:opacity-60 aria-[invalid=true]:border-danger";

export function Field({
  id,
  label,
  error,
  hint,
  children,
}: {
  id: string;
  label: string;
  error?: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-lavender-soft">
        {label}
      </label>
      {children}
      {hint && !error ? <p className="text-xs text-mist">{hint}</p> : null}
      {error ? (
        <p id={`${id}-error`} className="text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function Spinner({ label }: { label: string }) {
  return (
    <div role="status" className="flex items-center gap-3 text-mist">
      <span className="size-4 animate-spin rounded-full border-2 border-lavender/30 border-t-lavender" aria-hidden />
      <span>{label}</span>
    </div>
  );
}
