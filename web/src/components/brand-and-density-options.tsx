"use client";

import { useId, useState } from "react";

import { CloseIcon } from "@/components/icons";
import type { Density } from "@/lib/stations";

const DENSITIES: { value: Density; label: string; hint: string }[] = [
  { value: "few", label: "Pocas", hint: "unas 5" },
  { value: "normal", label: "Normal", hint: "unas 8" },
  { value: "many", label: "Muchas", hint: "unas 14" },
];

/** Cuántas recomendadas ver (10e). */
export function DensityOptions({ density, onChange }: { density: Density; onChange: (d: Density) => void }) {
  return (
    <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
      <legend className="text-[17px] font-bold">Cuántas recomendadas ver</legend>
      <p className="m-0 text-sm text-muted">Las demás siguen en «Ver todas» y como puntos en el mapa.</p>
      <div className="flex flex-wrap gap-1.5">
        {DENSITIES.map((d) => (
          <button
            key={d.value}
            type="button"
            aria-pressed={density === d.value}
            onClick={() => onChange(d.value)}
            className={`h-10 rounded-field border-[1.5px] px-3 text-sm font-semibold ${
              density === d.value ? "border-accent text-accent" : "border-field-border hover:bg-rule-soft"
            }`}
          >
            {d.label} <span className="font-normal text-muted">· {d.hint}</span>
          </button>
        ))}
      </div>
    </fieldset>
  );
}

/** Marcas que el usuario no quiere ver (10e): fuera de la lista, el mapa y el planificador. */
export function ExcludedBrandsOptions({
  brands,
  onChange,
  suggestions,
}: {
  brands: string[];
  onChange: (brands: string[]) => void;
  suggestions: readonly string[];
}) {
  const ids = useId();
  const [draft, setDraft] = useState("");
  const add = () => {
    const brand = draft.trim();
    if (brand && !brands.some((b) => b.toLowerCase() === brand.toLowerCase())) onChange([...brands, brand]);
    setDraft("");
  };
  return (
    <div className="flex flex-col gap-2">
      <div>
        <h3 className="m-0 text-[17px] font-bold">Marcas que no quiero</h3>
        <p className="m-0 mt-0.5 text-sm text-muted">
          No aparecerán en la lista, en el mapa ni en el planificador.
        </p>
      </div>
      {brands.length > 0 ? (
        <ul className="m-0 flex list-none flex-wrap gap-1.5 p-0" aria-label="Marcas excluidas">
          {brands.map((brand) => (
            <li key={brand}>
              <button
                type="button"
                aria-label={`Volver a mostrar ${brand}`}
                onClick={() => onChange(brands.filter((b) => b !== brand))}
                className="inline-flex h-10 items-center gap-1.5 rounded-field border-[1.5px] border-ink px-3 text-sm font-semibold hover:bg-rule-soft"
              >
                {brand} <CloseIcon size={14} />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          add();
        }}
      >
        <label className="sr-only" htmlFor={`${ids}-brand`}>
          Marca que no quiero
        </label>
        <input
          id={`${ids}-brand`}
          list={`${ids}-list`}
          value={draft}
          placeholder="Marca (p. ej. Shell)"
          onChange={(e) => setDraft(e.target.value)}
          className="h-11 min-w-0 flex-1 rounded-field border-[1.5px] border-field-border bg-surface px-3 text-[15px] font-semibold"
        />
        <datalist id={`${ids}-list`}>
          {suggestions.map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>
        <button
          type="submit"
          disabled={!draft.trim()}
          className="h-11 rounded-field border-[1.5px] border-field-border px-3.5 text-sm font-semibold hover:bg-rule-soft disabled:opacity-50"
        >
          Quitar marca
        </button>
      </form>
    </div>
  );
}
