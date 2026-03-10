import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  env: {
    INTERNAL_API_URL: process.env.INTERNAL_API_URL || "http://localhost:8004",
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8004",
    NEXT_PUBLIC_SHELL_DASHBOARD_URL:
      process.env.NEXT_PUBLIC_SHELL_DASHBOARD_URL ||
      "https://shell-production-3509.up.railway.app/dashboard",
  },
};

export default nextConfig;
