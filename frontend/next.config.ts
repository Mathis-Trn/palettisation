import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Image Docker autonome (server.js + dépendances minimales), voir frontend/Dockerfile.
  output: "standalone",
};

export default nextConfig;
