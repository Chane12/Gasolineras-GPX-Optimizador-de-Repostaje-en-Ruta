"use client";

import { useState } from "react";

import { StationRow } from "@/components/station-row";

const EXAMPLE_STATIONS = [
  {
    id: "a",
    name: "Repsol",
    kmOnRoute: 42,
    price: 1.659,
    town: "Arganda del Rey",
    schedule: "24 h",
    detourKm: 1.2,
  },
  {
    id: "b",
    name: "Ballenoil",
    kmOnRoute: 118,
    price: 1.639,
    town: "Tarancón",
    schedule: "24 h",
    detourKm: 0.4,
    cheapest: true,
  },
  {
    id: "c",
    name: "Cepsa",
    kmOnRoute: 205,
    price: 1.712,
    town: "Motilla del Palancar",
    schedule: "7–22 h",
    detourKm: null,
    dimmed: true,
  },
];

/** Lista de ejemplo con paradas que se pueden añadir y quitar (solo para el catálogo). */
export function DemoStationList() {
  const [inPlan, setInPlan] = useState<Set<string>>(new Set(["b"]));

  const toggle = (id: string) =>
    setInPlan((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <ul className="m-0 list-none p-0">
      {EXAMPLE_STATIONS.map(({ id, ...station }) => (
        <StationRow key={id} {...station} inPlan={inPlan.has(id)} onTogglePlan={() => toggle(id)} />
      ))}
    </ul>
  );
}
