// E2E: registro → concesión de créditos (admin) → generación en el estudio → pista completada y reproducible.
// Requiere: API en API_URL (por defecto http://127.0.0.1:8000), worker activo, web en BASE_URL (http://127.0.0.1:3000),
// y un administrador con SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD (variables E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD).
// Playwright se carga desde PLAYWRIGHT_MODULE si se define (p. ej. una instalación global); si no, desde node_modules.
const pw = await import(process.env.PLAYWRIGHT_MODULE ?? "playwright");
const chromium = pw.chromium ?? pw.default.chromium;

const BASE_URL = process.env.BASE_URL ?? "http://127.0.0.1:3000";
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? "admin@example.com";
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "admin-local-12345";
const SHOTS = process.env.E2E_SHOTS ?? "";

const log = (...a) => console.log("[e2e]", ...a);
const fail = (msg) => {
  console.error("[e2e] FAIL:", msg);
  process.exit(1);
};

async function adminSession() {
  const res = await fetch(`${API_URL}/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: ADMIN_EMAIL, password: ADMIN_PASSWORD }),
  });
  if (!res.ok) fail(`login admin ${res.status}`);
  const cookie = res.headers.get("set-cookie")?.split(";")[0];
  if (!cookie) fail("admin sin cookie de sesión");
  return cookie;
}

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await context.newPage();
page.setDefaultTimeout(20_000);

try {
  const email = `e2e-${Date.now()}@example.com`;
  log("registro", email);
  await page.goto(`${BASE_URL}/es/register`);
  await page.getByLabel("Nombre para mostrar").fill("E2E Tester");
  await page.getByLabel("Correo electrónico").fill(email);
  await page.getByLabel("Contraseña").fill("contraseña-e2e-123");
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await page.waitForURL(`${BASE_URL}/es/studio`);

  const me = await (await context.request.get(`${BASE_URL}/v1/auth/me`)).json();
  log("usuario creado", me.id);

  // Concesión de créditos por administrador (ajuste auditado, como en producción).
  const adminCookie = await adminSession();
  const adjust = await fetch(`${API_URL}/v1/admin/users/${me.id}/credit-adjustments`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Cookie: adminCookie },
    body: JSON.stringify({ delta: 20, reason: "Saldo de prueba E2E", idempotency_key: `e2e-${me.id}` }),
  });
  if (!adjust.ok) fail(`ajuste de créditos ${adjust.status}`);
  log("créditos concedidos", await adjust.json());

  await page.reload();
  await page.getByLabel("Descripción").fill("Piano lento y pads cálidos, atmósfera nocturna de lluvia en la ciudad");
  await page.getByLabel("Duración (segundos)").fill("2");
  await page.getByLabel("Género").selectOption("ambient");
  await page.getByLabel("Piano").check({ force: true }).catch(() => undefined);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/studio-form.png`, fullPage: true });

  await page.getByRole("button", { name: "Generar música" }).click();
  log("generación enviada");

  // La pista debe completarse en segundo plano; el sondeo actualiza el estado sin recargar.
  await page.getByText("Completada", { exact: true }).waitFor({ timeout: 60_000 });
  log("estado: Completada");

  const audio = page.locator("audio");
  await audio.waitFor({ state: "attached" });
  await page.waitForFunction(() => {
    const el = document.querySelector("audio");
    return el && el.getAttribute("src") && el.getAttribute("src").includes("/v1/tracks/");
  });
  const src = await audio.getAttribute("src");
  log("audio src", src?.slice(0, 60));

  const file = await context.request.get(`${BASE_URL}${src}`);
  if (!file.ok()) fail(`descarga ${file.status()}`);
  const bytes = await file.body();
  if (bytes.subarray(0, 4).toString() !== "RIFF") fail("el archivo descargado no es WAV");
  log(`archivo WAV válido: ${bytes.length} bytes`);

  const wallet = await (await context.request.get(`${BASE_URL}/v1/wallet`)).json();
  if (wallet.available_credits !== 19 || wallet.reserved_credits !== 0) fail(`saldo inesperado ${JSON.stringify(wallet)}`);
  log("saldo tras consumo:", wallet);

  if (SHOTS) await page.screenshot({ path: `${SHOTS}/studio-completed.png`, fullPage: true });
  log("OK: flujo completo verificado");
} catch (err) {
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/failure.png`, fullPage: true }).catch(() => undefined);
  fail(err?.message ?? String(err));
} finally {
  await browser.close();
}
