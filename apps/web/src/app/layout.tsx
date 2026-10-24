import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "InsightHR",
  description: "AI-assisted employee performance management",
};

// CSP nonces belong to one request, never to a prerendered HTML document.
export const dynamic = "force-dynamic";

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="vi">
      <body><Providers>{children}</Providers></body>
    </html>
  );
}

