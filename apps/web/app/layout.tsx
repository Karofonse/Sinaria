import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Sonaria", template: "%s · Sonaria" },
  description: "Genera música instrumental original con inteligencia artificial.",
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: "#0a0e22",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // El idioma real se fija en app/[locale]/layout.tsx mediante el proveedor de i18n.
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
