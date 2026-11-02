import { NextResponse, type NextRequest } from "next/server";

const LOCALES = ["es", "en"] as const;
const DEFAULT_LOCALE = "es";
const PROTECTED = ["studio", "library", "dashboard", "billing", "profile", "admin"];

// Esta redirección es solo de experiencia de usuario. La autorización real la hace la API en cada petición.
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const segments = pathname.split("/").filter(Boolean);
  const first = segments[0];

  if (!first || !(LOCALES as readonly string[]).includes(first)) {
    const cookieLocale = request.cookies.get("sonaria_locale")?.value;
    const accept = request.headers.get("accept-language") ?? "";
    const locale =
      cookieLocale && (LOCALES as readonly string[]).includes(cookieLocale)
        ? cookieLocale
        : accept.toLowerCase().startsWith("en")
          ? "en"
          : DEFAULT_LOCALE;
    const url = request.nextUrl.clone();
    url.pathname = `/${locale}${pathname === "/" ? "" : pathname}`;
    return NextResponse.redirect(url);
  }

  const section = segments[1];
  const hasSession = request.cookies.has("sonaria_session");
  if (section && PROTECTED.includes(section) && !hasSession) {
    const url = request.nextUrl.clone();
    url.pathname = `/${first}/login`;
    url.search = `?next=${encodeURIComponent(pathname)}`;
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!v1|_next|favicon.ico|robots.txt|sitemap.xml|.*\\..*).*)"],
};
