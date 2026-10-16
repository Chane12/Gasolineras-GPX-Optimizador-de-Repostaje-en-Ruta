"use client";

import dynamic from "next/dynamic";

/** El mapa (MapLibre, ~1 MB) se carga aparte y solo en el navegador: no retrasa el resto de la página. */
export const RouteMapLazy = dynamic(
  () => import("@/components/route-map/route-map").then((m) => m.RouteMap),
  { ssr: false, loading: () => <div className="size-full bg-map-land" aria-hidden="true" /> },
);
