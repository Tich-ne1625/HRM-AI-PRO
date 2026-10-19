import type { NextConfig } from "next";

const internal = new URL(process.env.API_INTERNAL_URL ?? "http://localhost:8000");
if (!["http:", "https:"].includes(internal.protocol) || internal.username || internal.password ||
    internal.pathname !== "/" || internal.search || internal.hash) {
  throw new Error("API_INTERNAL_URL must be one HTTP(S) origin without credentials");
}

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${internal.origin}/api/v1/:path*` }];
  },
};

export default nextConfig;

