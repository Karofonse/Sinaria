import { describe, expect, it } from "vitest";
import es from "@/messages/es.json";
import en from "@/messages/en.json";
import { interpolate, lookup, type Messages } from "@/lib/i18n";

function leafKeys(obj: Messages, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([k, v]) => {
    const path = prefix ? `${prefix}.${k}` : k;
    if (typeof v === "object" && !Array.isArray(v)) return leafKeys(v as Messages, path);
    return [path];
  });
}

describe("diccionarios", () => {
  it("español e inglés tienen exactamente las mismas claves", () => {
    expect(leafKeys(en as Messages).sort()).toEqual(leafKeys(es as Messages).sort());
  });

  it("no hay valores vacíos", () => {
    for (const key of leafKeys(es as Messages)) {
      expect(lookup(es as Messages, key).trim().length, key).toBeGreaterThan(0);
    }
  });

  it("lookup devuelve la clave si falta y interpola variables", () => {
    expect(lookup(es as Messages, "no.existe")).toBe("no.existe");
    expect(interpolate("Hola {name}", { name: "Ana" })).toBe("Hola Ana");
  });
});
