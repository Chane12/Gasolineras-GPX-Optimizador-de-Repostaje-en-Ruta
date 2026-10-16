import type { Metadata } from "next";
import { Suspense } from "react";

import { RouteResults } from "./route-results";

export const metadata: Metadata = {
  title: "Gasolineras en tu ruta · Gasolineras en Ruta",
  // Resultados de cada búsqueda: no son páginas para los buscadores.
  robots: { index: false, follow: true },
};

export default function RoutePage() {
  return (
    <Suspense fallback={<div className="h-dvh bg-map-land" />}>
      <RouteResults />
    </Suspense>
  );
}
