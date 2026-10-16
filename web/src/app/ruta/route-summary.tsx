"use client";

import { useQueryStates } from "nuqs";

import { normalizeOptions, searchParams } from "@/lib/search-params";

/**
 * Provisional (pasos 6–7 del plan): muestra la búsqueda leída de la URL. Aquí irán el mapa y la lista.
 */
export function RouteSummary() {
  const [params] = useQueryStates(searchParams);
  const options = normalizeOptions(params);

  const route = params.demo
    ? "Ruta de ejemplo por la Sierra de Gredos"
    : params.gpx
      ? "Tu ruta GPX"
      : params.origen && params.destino
        ? `${params.origen} → ${params.destino}`
        : null;

  if (!route) {
    return <p className="m-0">Falta la ruta: vuelve al inicio y escribe origen y destino o sube tu GPX.</p>;
  }

  return (
    <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[15px]">
      <dt className="text-muted">Ruta</dt>
      <dd className="m-0 font-bold">{route}</dd>
      <dt className="text-muted">Combustible</dt>
      <dd className="m-0">{params.combustible}</dd>
      <dt className="text-muted">Distancia</dt>
      <dd className="m-0">hasta {options.radio} km</dd>
      <dt className="text-muted">Autonomía</dt>
      <dd className="m-0">{options.autonomia ? `${options.autonomia} km` : "sin aviso"}</dd>
    </dl>
  );
}
