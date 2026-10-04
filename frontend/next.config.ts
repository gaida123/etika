import type { NextConfig } from "next";

// FastAPI backend (backend/README: uvicorn app.api.main:app). The proxy keeps the browser on one
// origin, so the backend needs no CORS setup.
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // The local app is commonly opened as either localhost or 127.0.0.1. Allow
  // both in development so Next can load its client resources and hydrate the
  // intake wizard rather than falling back to native form submission.
  allowedDevOrigins: ["localhost", "127.0.0.1"],
  // Keep Next's resolver and production-file tracing inside this independently
  // deployable frontend. A parent-directory package lock must not change either.
  turbopack: {
    root: __dirname,
  },
  outputFileTracingRoot: __dirname,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
};

export default nextConfig;
