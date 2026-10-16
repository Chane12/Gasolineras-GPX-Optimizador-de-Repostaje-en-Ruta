import type { Metadata } from "next";
import { Suspense } from "react";

import { RouteResults } from "./route-results";

export const metadata: Metadata = {
  title: "Gasolineras en tu ruta · Gasolineras en Ruta",
};

export default function RoutePage() {
  return (
    <Suspense fallback={<div className="h-dvh bg-map-land" />}>
      <RouteResults />
    </Suspense>
  );
}
