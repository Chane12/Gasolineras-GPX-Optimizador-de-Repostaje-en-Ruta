"use client";

import { useId, useState } from "react";

import { CheckIcon, ChevronDownIcon } from "@/components/icons";
import { LIMITS } from "@/lib/search-params";

export interface Filters {
  /** Distancia máxima a la ruta (km). */
  radio: number;
  abierta24h: boolean;
  /** "Ver también las de paso" (antes "Modo España Vaciada"). */
  vaciada: boolean;
  /** Autonomía en km; 0 = sin aviso. */
  autonomia: number;
}

const RADIO_CHOICES = [1, 2, 3, 5, 8, 10, 15];
const PROFILES = [
  { label: "Moto", km: 250 },
  { label: "Coche", km: 600 },
  { label: "Gran autonomía", km: 900 },
] as const;

const chip =
  "inline-flex h-10 shrink-0 cursor-pointer items-center gap-1.5 rounded-field border-[1.5px] bg-surface px-3 text-sm font-semibold whitespace-nowrap";
const chipOff = "border-field-border text-ink hover:bg-rule-soft";
const chipOn = "border-accent text-accent";

function Toggle({ on, onClick, children }: { on: boolean; onClick: () => void; children: string }) {
  return (
    <button type="button" aria-pressed={on} onClick={onClick} className={`${chip} ${on ? chipOn : chipOff}`}>
      {on ? <CheckIcon size={14} /> : null}
      {children}
    </button>
  );
}

/**
 * Filtros de la ruta (maquetas Escritorio-Ruta y Movil-Resultados): se aplican al momento, con frases de
 * conductor. La autonomía es opcional: al activarla se elige el vehículo o los km.
 */
export function FilterBar({
  filters,
  onChange,
}: {
  filters: Filters;
  onChange: (next: Partial<Filters>) => void;
}) {
  const ids = useId();
  const [autonomyOpen, setAutonomyOpen] = useState(false);
  const [customKm, setCustomKm] = useState("");
  const custom = Number.parseInt(customKm, 10);
  const customValid =
    Number.isFinite(custom) && custom >= LIMITS.autonomiaKm.min && custom <= LIMITS.autonomiaKm.max;

  return (
    <div className="flex flex-col gap-2.5">
      <div
        role="group"
        aria-label="Filtros"
        className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-0.5 lg:mx-0 lg:flex-wrap lg:overflow-visible lg:px-0"
      >
        <span
          className={`${chip} ${chipOff} relative pr-2 focus-within:outline-3 focus-within:outline-accent`}
        >
          <span aria-hidden="true">
            Hasta <span className="font-mono">{filters.radio}</span> km de desvío
          </span>
          <ChevronDownIcon size={14} aria-hidden="true" />
          <select
            aria-label="Distancia máxima a la ruta"
            className="absolute inset-0 cursor-pointer opacity-0"
            value={filters.radio}
            onChange={(e) => onChange({ radio: Number(e.target.value) })}
          >
            {RADIO_CHOICES.map((km) => (
              <option key={km} value={km}>
                Hasta {km} km de desvío
              </option>
            ))}
          </select>
        </span>
        <Toggle on={filters.abierta24h} onClick={() => onChange({ abierta24h: !filters.abierta24h })}>
          Solo abiertas 24 h
        </Toggle>
        <Toggle on={filters.vaciada} onClick={() => onChange({ vaciada: !filters.vaciada })}>
          Ver también las de paso
        </Toggle>
        <button
          type="button"
          aria-expanded={autonomyOpen}
          aria-controls={`${ids}-autonomy`}
          onClick={() => setAutonomyOpen((open) => !open)}
          className={`${chip} ${filters.autonomia > 0 ? chipOn : chipOff}`}
        >
          {filters.autonomia > 0 ? <CheckIcon size={14} /> : null}
          {filters.autonomia > 0 ? (
            <span>
              Autonomía <span className="font-mono">{filters.autonomia}</span> km
            </span>
          ) : (
            "Avisar de mi autonomía"
          )}
        </button>
      </div>

      {autonomyOpen ? (
        <fieldset
          id={`${ids}-autonomy`}
          className="m-0 flex flex-col gap-2 border-0 border-y border-rule p-0 py-3"
        >
          <legend className="float-left mb-1 text-sm font-bold">
            Te avisamos de los tramos más largos que tu autonomía
          </legend>
          <div className="clear-both flex flex-wrap gap-2">
            {PROFILES.map((p) => (
              <button
                key={p.km}
                type="button"
                aria-pressed={filters.autonomia === p.km}
                onClick={() => onChange({ autonomia: p.km })}
                className={`${chip} ${filters.autonomia === p.km ? chipOn : chipOff}`}
              >
                {p.label} · <span className="font-mono">{p.km}</span> km
              </button>
            ))}
            <form
              className="flex items-center gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (customValid) onChange({ autonomia: custom });
              }}
            >
              <label className="sr-only" htmlFor={`${ids}-km`}>
                Otra autonomía, en km
              </label>
              <input
                id={`${ids}-km`}
                inputMode="numeric"
                placeholder="Otra (km)"
                value={customKm}
                onChange={(e) => setCustomKm(e.target.value.replace(/\D/g, ""))}
                className="h-10 w-28 rounded-field border-[1.5px] border-field-border bg-surface px-3 font-mono text-sm"
              />
              <button
                type="submit"
                disabled={!customValid}
                className={`${chip} ${chipOff} disabled:opacity-50`}
              >
                Usar
              </button>
            </form>
          </div>
          {filters.autonomia > 0 ? (
            <button
              type="button"
              onClick={() => onChange({ autonomia: 0 })}
              className="self-start py-2 text-[15px] font-bold text-accent hover:text-accent-strong"
            >
              Quitar el aviso de autonomía
            </button>
          ) : null}
        </fieldset>
      ) : null}
    </div>
  );
}
