export const locales = ["es", "en"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "es";

export function isLocale(value: string): value is Locale {
  return (locales as readonly string[]).includes(value);
}

export type Messages = { [key: string]: string | string[] | Messages };

export async function getMessages(locale: Locale): Promise<Messages> {
  const mod = locale === "en" ? await import("@/messages/en.json") : await import("@/messages/es.json");
  return mod.default as Messages;
}

/** Resuelve una clave con puntos ("studio.title") sobre el diccionario. Devuelve la clave si falta. */
export function lookup(messages: Messages, key: string): string {
  let node: Messages | string | string[] | undefined = messages;
  for (const part of key.split(".")) {
    if (typeof node !== "object" || node === null || Array.isArray(node)) return key;
    node = (node as Messages)[part];
  }
  return typeof node === "string" ? node : key;
}

export function interpolate(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_, name: string) => String(vars[name] ?? `{${name}}`));
}
