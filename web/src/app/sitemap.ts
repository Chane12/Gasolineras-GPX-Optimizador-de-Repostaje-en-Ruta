import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/site";

/** Solo las páginas fijas: los resultados dependen de cada búsqueda y no se indexan. */
export default function sitemap(): MetadataRoute.Sitemap {
  return ["", "/fuentes", "/privacidad"].map((path) => ({
    url: `${SITE_URL}${path}`,
    changeFrequency: "monthly",
    priority: path === "" ? 1 : 0.3,
  }));
}
