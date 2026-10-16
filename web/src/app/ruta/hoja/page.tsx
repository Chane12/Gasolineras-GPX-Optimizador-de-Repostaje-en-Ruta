import type { Metadata } from "next";
import { Suspense } from "react";

import { RoadbookView } from "./roadbook-view";

export const metadata: Metadata = {
  title: "Hoja de ruta · Gasolineras en Ruta",
};

export default function RoadbookPage() {
  return (
    <Suspense fallback={<div className="min-h-dvh" />}>
      <RoadbookView />
    </Suspense>
  );
}
