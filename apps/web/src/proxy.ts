import { NextRequest, NextResponse } from "next/server";

export function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const development = process.env.NODE_ENV === "development";
  const https = process.env.APP_ENV === "production" && process.env.WEB_ORIGIN?.startsWith("https://");
  const policy = ["default-src 'self'", `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${development ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'", "img-src 'self' data: blob:", "font-src 'self' data:",
    `connect-src 'self'${development ? " ws: wss:" : ""}`, "object-src 'none'", "base-uri 'none'",
    "form-action 'self'", "frame-ancestors 'none'", ...(https ? ["upgrade-insecure-requests"] : [])].join("; ");
  const headers = new Headers(request.headers);
  headers.set("x-nonce", nonce);
  headers.set("Content-Security-Policy", policy);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set("Content-Security-Policy", policy);
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set("Cache-Control", "no-store");
  if (https) response.headers.set("Strict-Transport-Security", "max-age=31536000");
  return response;
}

export const config = { matcher: ["/((?!api/|_next/|favicon.ico|robots.txt|sitemap.xml).*)"] };
