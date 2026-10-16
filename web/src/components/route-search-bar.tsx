"use client";

import Link from "next/link";
import { type FormEvent, useId, useState } from "react";

import { Button } from "@/components/button";
import { SwapIcon } from "@/components/icons";
import { PlaceInput, type PlaceValue } from "@/components/place-input";
import { PlaceProblemMessage } from "@/components/place-problem";
import { api, type ApiClient } from "@/lib/api/client";
import { useFuels } from "@/lib/api/queries";
import { DEFAULT_FUEL, type FuelId } from "@/lib/search-params";
import { type PlaceProblem, type PlaceRole, type RouteEnd, usePlaceCheck } from "@/lib/use-place-check";

const OriginMarker = <span className="size-3 rounded-full border-[2.5px] border-accent" />;
const DestinationMarker = <span className="size-3 bg-accent" />;

export interface RouteSearchBarProps {
  /** Origen y destino actuales; null en una ruta GPX o de ejemplo (no se editan aquí). */
  places: { origen: PlaceValue; destino: PlaceValue } | null;
  /** Nombre de la ruta cuando no es de origen y destino ("Tu ruta GPX"…). */
  routeName: string;
  fuel: FuelId;
  onFuelChange: (fuel: FuelId) => void;
  onSearch: (ends: { origen: RouteEnd; destino: RouteEnd }) => void;
  /** Fila (cabecera del ordenador) o columna (diálogo "Cambiar" del móvil). */
  layout: "row" | "column";
  client?: ApiClient;
}

/**
 * La búsqueda, siempre editable en la pantalla de la ruta (maqueta Escritorio-Ruta): el combustible cambia
 * al momento; origen y destino, al pulsar "Buscar" (con las mismas comprobaciones que el inicio).
 */
export function RouteSearchBar({
  places,
  routeName,
  fuel,
  onFuelChange,
  onSearch,
  layout,
  client = api,
}: RouteSearchBarProps) {
  const ids = useId();
  const fuels = useFuels(client);
  const checkPlace = usePlaceCheck(client);
  const [origen, setOrigen] = useState<PlaceValue>(places?.origen ?? { text: "" });
  const [destino, setDestino] = useState<PlaceValue>(places?.destino ?? { text: "" });
  const [problems, setProblems] = useState<Partial<Record<PlaceRole, PlaceProblem>>>({});
  const [busy, setBusy] = useState(false);

  const values = { origen, destino };
  const setters = { origen: setOrigen, destino: setDestino };
  const row = layout === "row";

  function edit(role: PlaceRole, value: PlaceValue) {
    setters[role](value);
    if (problems[role]) setProblems((p) => ({ ...p, [role]: undefined }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    try {
      const [o, d] = await Promise.all([checkPlace("origen", origen), checkPlace("destino", destino)]);
      setProblems({ origen: o.problem, destino: d.problem });
      if (o.end && d.end) onSearch({ origen: o.end, destino: d.end });
    } finally {
      setBusy(false);
    }
  }

  const fuelSelect = (
    <label className={row ? "shrink-0" : "flex flex-col gap-1 text-sm font-bold"}>
      <span className={row ? "sr-only" : undefined}>Combustible</span>
      <select
        className="h-11 w-full rounded-field border-[1.5px] border-field-border bg-surface px-3 text-base font-semibold text-ink"
        value={fuel}
        onChange={(e) => onFuelChange(e.target.value as FuelId)}
      >
        {fuels.data ? (
          fuels.data.map((f) => (
            <option key={f.id} value={f.id}>
              {f.label}
            </option>
          ))
        ) : (
          <option value={fuel}>{fuel === DEFAULT_FUEL ? "Gasolina 95" : fuel}</option>
        )}
      </select>
    </label>
  );

  if (!places) {
    return (
      <div className={row ? "flex min-w-0 flex-1 flex-wrap items-center gap-3" : "flex flex-col gap-3"}>
        <span className="min-w-0 truncate text-base font-bold">{routeName}</span>
        {fuelSelect}
        <Link href="/" className="py-2 text-[15px] font-bold">
          Nueva búsqueda
        </Link>
      </div>
    );
  }

  const problemList = (["origen", "destino"] as const).flatMap((role) => {
    const problem = problems[role];
    return problem
      ? [
          <PlaceProblemMessage
            key={role}
            id={`${ids}-${role}-msg`}
            problem={problem}
            onPick={(place) => edit(role, { text: place.name, place })}
          />,
        ]
      : [];
  });

  return (
    <form
      onSubmit={submit}
      noValidate
      aria-label="Tu búsqueda"
      className={row ? "flex min-w-0 flex-1 flex-col gap-2" : "flex flex-col gap-3.5"}
    >
      <div className={row ? "flex min-w-0 flex-wrap items-center gap-2" : "flex flex-col gap-3.5"}>
        <div className={row ? "min-w-44 flex-1" : undefined}>
          <PlaceInput
            label="Origen"
            hideLabel={row}
            marker={OriginMarker}
            value={values.origen}
            onChange={(v) => edit("origen", v)}
            invalid={Boolean(problems.origen)}
            describedBy={problems.origen ? `${ids}-origen-msg` : undefined}
            enterKeyHint="next"
            client={client}
          />
        </div>
        <button
          type="button"
          aria-label="Intercambiar origen y destino"
          title="Intercambiar origen y destino"
          onClick={() => {
            setOrigen(destino);
            setDestino(origen);
            setProblems({ origen: problems.destino, destino: problems.origen });
          }}
          className={`inline-flex size-11 shrink-0 items-center justify-center rounded-field border-[1.5px] border-rule text-ink hover:bg-rule-soft ${
            row ? "" : "self-end"
          }`}
        >
          <SwapIcon size={18} className={row ? "rotate-90" : undefined} />
        </button>
        <div className={row ? "min-w-44 flex-1" : undefined}>
          <PlaceInput
            label="Destino"
            hideLabel={row}
            marker={DestinationMarker}
            value={values.destino}
            onChange={(v) => edit("destino", v)}
            invalid={Boolean(problems.destino)}
            describedBy={problems.destino ? `${ids}-destino-msg` : undefined}
            enterKeyHint="search"
            client={client}
          />
        </div>
        {fuelSelect}
        <Button type="submit" disabled={busy} size={row ? "md" : "lg"} block={!row}>
          {busy ? "Buscando…" : "Buscar"}
        </Button>
      </div>
      {problemList.length > 0 ? <div className="flex flex-col gap-2">{problemList}</div> : null}
    </form>
  );
}
