import type { NextConfig } from "next";

// FastAPI backend (backend/README: uvicorn app.api.main:app). The proxy keeps the browser on one
// origin, so the backend needs no CORS setup.
const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/:path*` }];
  },
};

export default nextConfig;
