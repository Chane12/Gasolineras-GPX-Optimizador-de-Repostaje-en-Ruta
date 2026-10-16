import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Las instrucciones para agentes están en web/CLAUDE.md: que `next dev` no cree un AGENTS.md aparte.
  agentRules: false,
};

export default nextConfig;
