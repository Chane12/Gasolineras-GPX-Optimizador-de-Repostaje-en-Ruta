import type { NextConfig } from "next";

/**
 * Hasta el lanzamiento (punto 11 del plan) la web publicada es de pruebas: que no la indexen los buscadores.
 * Para abrirla, `SITE_INDEXABLE=true` en las variables del proyecto de Vercel (producción).
 */
export function robotsHeaders(indexable = process.env.SITE_INDEXABLE === "true") {
  return indexable
    ? []
    : [{ source: "/:path*", headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }] }];
}

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Las instrucciones para agentes están en web/CLAUDE.md: que `next dev` no cree un AGENTS.md aparte.
  agentRules: false,
  headers: async () => robotsHeaders(),
};

export default nextConfig;
