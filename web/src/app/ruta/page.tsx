import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { SiteHeader } from "@/components/site-header";

import { RouteSummary } from "./route-summary";

export const metadata: Metadata = {
  title: "Gasolineras en tu ruta · Gasolineras en Ruta",
};

export default function RoutePage() {
  return (
    <div className="mx-auto flex min-h-dvh max-w-xl flex-col">
      <SiteHeader />
      <main className="flex flex-col gap-4 px-4 py-6">
        <h1 className="m-0 text-2xl font-bold">Elige tus paradas</h1>
        <p className="m-0 text-muted">Los resultados con el mapa llegan en el siguiente paso de la web.</p>
        <Suspense fallback={null}>
          <RouteSummary />
        </Suspense>
        <Link href="/" className="font-semibold">
          Cambiar la búsqueda
        </Link>
      </main>
    </div>
  );
}
