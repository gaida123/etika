import type { NextConfig } from "next";

// FastAPI backend (backend/README: uvicorn app.api.main:app). The proxy keeps the browser on one
// origin, so the backend needs no CORS setup.
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // The local app is commonly opened as either localhost or 127.0.0.1. Allow
  // both in development so Next can load its client resources and hydrate the
  // intake wizard rather than falling back to native form submission.
  allowedDevOrigins: ["localhost", "127.0.0.1"],
  // No floating Next.js badge in the corner during development.
  devIndicators: false,
  // Keep Next's resolver and production-file tracing inside this independently
  // deployable frontend. A parent-directory package lock must not change either.
  turbopack: {
    root: __dirname,
  },
  outputFileTracingRoot: __dirname,
  experimental: {
    // Live assessments queue each agent's Gemini report (up to 60s per call), so they can run
    // well past the proxy's 30s default. Without this the browser sees a failed check.
    proxyTimeout: 180_000,
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
};

export default nextConfig;
