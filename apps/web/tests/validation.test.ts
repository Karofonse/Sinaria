import { describe, expect, it } from "vitest";
import { buildGenerationSchema, toGenerationPayload, isTerminal } from "@/lib/validation";

const caps = { min_duration_s: 1, max_duration_s: 120, supports_seed: true, supports_negative_prompt: false };
const base = { prompt: "piano suave", negativePrompt: "", genre: "", mood: "", instruments: [], durationSeconds: 30, seed: "" };

describe("validación del estudio", () => {
  const schema = buildGenerationSchema(caps);

  it("acepta una descripción válida y normaliza espacios", () => {
    const parsed = schema.parse({ ...base, prompt: "   piano   suave  " });
    expect(parsed.prompt).toBe("piano suave");
  });

  it("rechaza descripciones demasiado cortas", () => {
    const result = schema.safeParse({ ...base, prompt: "ab" });
    expect(result.success).toBe(false);
    if (!result.success) expect(result.error.issues[0].message).toBe("studio.promptRequired");
  });

  it("respeta el rango de duración del modelo", () => {
    expect(schema.safeParse({ ...base, durationSeconds: 121 }).success).toBe(false);
    expect(schema.safeParse({ ...base, durationSeconds: 0 }).success).toBe(false);
    expect(schema.safeParse({ ...base, durationSeconds: 120 }).success).toBe(true);
  });

  it("valida la semilla como entero sin signo de 32 bits", () => {
    expect(schema.safeParse({ ...base, seed: "4294967296" }).success).toBe(false);
    expect(schema.safeParse({ ...base, seed: "-1" }).success).toBe(false);
    expect(schema.safeParse({ ...base, seed: "42" }).success).toBe(true);
  });

  it("rechaza géneros e instrumentos fuera de catálogo", () => {
    expect(schema.safeParse({ ...base, genre: "rap" }).success).toBe(false);
    expect(schema.safeParse({ ...base, instruments: ["voz"] }).success).toBe(false);
  });
});

describe("payload", () => {
  it("omite el prompt negativo y la semilla cuando el modelo no los admite", () => {
    const payload = toGenerationPayload(
      "mock-music-small",
      { ...base, negativePrompt: "batería", seed: "7" },
      caps,
    );
    expect(payload.seed).toBe(7);
    const noSupport = toGenerationPayload("x", { ...base, negativePrompt: "batería", seed: "7" }, {
      ...caps,
      supports_seed: false,
      supports_negative_prompt: false,
    });
    expect(noSupport.negative_prompt).toBeNull();
    expect(noSupport.seed).toBeNull();
    expect(noSupport.instrumental).toBe(true);
  });

  it("identifica estados terminales", () => {
    expect(isTerminal("completed")).toBe(true);
    expect(isTerminal("failed")).toBe(true);
    expect(isTerminal("processing")).toBe(false);
  });
});
