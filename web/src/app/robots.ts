import type { MetadataRoute } from "next";

import { SITE_INDEXABLE, SITE_URL } from "@/lib/site";

/** robots.txt: cerrado mientras la web es de pruebas; abierto (salvo el catálogo de diseño) al lanzarla. */
export function robotsFor(indexable: boolean): MetadataRoute.Robots {
  if (!indexable) return { rules: { userAgent: "*", disallow: "/" } };
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/diseno", "/ruta"] },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}

export default function robots(): MetadataRoute.Robots {
  return robotsFor(SITE_INDEXABLE);
}
