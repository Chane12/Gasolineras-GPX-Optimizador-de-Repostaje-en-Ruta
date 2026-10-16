/** Dirección pública de la web (enlaces absolutos, Open Graph, sitemap). En Vercel, la de producción. */
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://gasolineras-web.vercel.app").replace(
  /\/$/,
  "",
);

/** Hasta el lanzamiento, la web no se indexa (ver también la cabecera X-Robots-Tag en next.config.ts). */
export const SITE_INDEXABLE = process.env.SITE_INDEXABLE === "true";
