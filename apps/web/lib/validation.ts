import { z } from "zod";

// Espejo de las reglas del servidor (schemas.GenerationCreate). El servidor sigue siendo la autoridad:
// esta validación solo evita viajes de ida y vuelta innecesarios. Los mensajes son claves de i18n.

export const GENRES = ["ambient", "lofi", "electronic", "cinematic", "jazz", "classical"] as const;
export const MOODS = ["calm", "dreamy", "energetic", "melancholic", "uplifting"] as const;
export const INSTRUMENTS = ["piano", "pads", "strings", "guitar", "synth", "drums", "bass", "vinyl"] as const;

export const MAX_PROMPT_CHARS = 2000;

export type ModelCaps = {
  min_duration_s: number;
  max_duration_s: number;
  supports_seed: boolean;
  supports_negative_prompt: boolean;
};

export function buildGenerationSchema(caps: ModelCaps) {
  return z.object({
    prompt: z
      .string()
      .transform((v) => v.trim().replace(/\s+/g, " "))
      .pipe(
        z
          .string()
          .min(3, { message: "studio.promptRequired" })
          .max(MAX_PROMPT_CHARS, { message: "studio.promptTooLong" }),
      ),
    negativePrompt: z.string().max(500).optional().default(""),
    genre: z.enum(GENRES).or(z.literal("")).default(""),
    mood: z.enum(MOODS).or(z.literal("")).default(""),
    instruments: z.array(z.enum(INSTRUMENTS)).max(10).default([]),
    durationSeconds: z
      .number({ message: "studio.durationInvalid" })
      .int({ message: "studio.durationInvalid" })
      .min(caps.min_duration_s, { message: "studio.durationInvalid" })
      .max(caps.max_duration_s, { message: "studio.durationInvalid" }),
    seed: z
      .union([
        z.literal(""),
        z
          .string()
          .regex(/^\d+$/, { message: "studio.seedInvalid" })
          .refine((v) => Number(v) <= 4294967295, { message: "studio.seedInvalid" }),
      ])
      .default(""),
  });
}

export type GenerationForm = z.input<ReturnType<typeof buildGenerationSchema>>;

/** Convierte el formulario validado en el cuerpo que espera POST /v1/generations. */
export function toGenerationPayload(
  modelKey: string,
  values: {
    prompt: string;
    negativePrompt: string;
    genre: string;
    mood: string;
    instruments: string[];
    durationSeconds: number;
    seed: string;
  },
  caps: ModelCaps,
) {
  return {
    model_key: modelKey,
    prompt: values.prompt.trim(),
    negative_prompt: caps.supports_negative_prompt && values.negativePrompt.trim() ? values.negativePrompt.trim() : null,
    genre: values.genre || null,
    mood: values.mood || null,
    instruments: values.instruments,
    duration_seconds: values.durationSeconds,
    seed: caps.supports_seed && values.seed !== "" ? Number(values.seed) : null,
    instrumental: true as const,
  };
}

export const TERMINAL_STATUSES = ["completed", "failed"] as const;

export function isTerminal(status: string): boolean {
  return (TERMINAL_STATUSES as readonly string[]).includes(status);
}

export const emailSchema = z.string().trim().toLowerCase().pipe(z.email({ message: "auth.invalidEmail" }));
export const passwordSchema = z.string().min(10, { message: "auth.passwordShort" });
export const nameSchema = z.string().trim().min(2, { message: "auth.nameShort" });
