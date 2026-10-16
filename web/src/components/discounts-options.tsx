"use client";

import { useId } from "react";

import { CloseIcon, PlusIcon } from "@/components/icons";
import { type Discount, isValidDiscount, MAX_CENTS, MAX_PERCENT } from "@/lib/discounts";

/** Mis descuentos (punto 10c): marca + céntimos/L o %. Las marcas de la ruta se sugieren al escribir. */
export function DiscountsOptions({
  discounts,
  onChange,
  brands,
}: {
  discounts: Discount[];
  onChange: (next: Discount[]) => void;
  /** Rótulos de las gasolineras de la ruta, para sugerir la marca. */
  brands: readonly string[];
}) {
  const ids = useId();
  const set = (i: number, patch: Partial<Discount>) =>
    onChange(discounts.map((d, j) => (j === i ? { ...d, ...patch } : d)));

  return (
    <div className="flex flex-col gap-3">
      <div>
        <h3 className="m-0 text-[17px] font-bold">Mis descuentos</h3>
        <p className="m-0 mt-0.5 text-sm text-muted">
          Si tienes una tarjeta o una app de descuento, ponla aquí: ordenamos y recomendamos por lo que
          pagarás tú. Se guarda en tu dispositivo.
        </p>
      </div>
      <datalist id={`${ids}-brands`}>
        {brands.map((b) => (
          <option key={b} value={b} />
        ))}
      </datalist>
      {discounts.length > 0 ? (
        <ul className="m-0 flex list-none flex-col gap-2 p-0">
          {discounts.map((d, i) => {
            const invalid = d.brand.trim() !== "" && d.value > 0 && !isValidDiscount(d);
            return (
              <li key={i} className="flex flex-wrap items-center gap-2">
                <label className="sr-only" htmlFor={`${ids}-brand-${i}`}>
                  Marca
                </label>
                <input
                  id={`${ids}-brand-${i}`}
                  list={`${ids}-brands`}
                  value={d.brand}
                  placeholder="Marca (p. ej. Repsol)"
                  onChange={(e) => set(i, { brand: e.target.value })}
                  className="h-11 min-w-0 flex-[1_1_140px] rounded-field border-[1.5px] border-field-border bg-surface px-3 text-[15px] font-semibold"
                />
                <label className="sr-only" htmlFor={`${ids}-value-${i}`}>
                  Descuento
                </label>
                <input
                  id={`${ids}-value-${i}`}
                  inputMode="decimal"
                  value={d.value || ""}
                  placeholder="0"
                  aria-invalid={invalid || undefined}
                  onChange={(e) =>
                    set(i, { value: Number(e.target.value.replace(",", ".").replace(/[^\d.]/g, "")) || 0 })
                  }
                  className="h-11 w-20 rounded-field border-[1.5px] border-field-border bg-surface px-3 font-mono text-sm"
                />
                <label className="sr-only" htmlFor={`${ids}-kind-${i}`}>
                  Tipo de descuento
                </label>
                <select
                  id={`${ids}-kind-${i}`}
                  value={d.kind}
                  onChange={(e) => set(i, { kind: e.target.value as Discount["kind"] })}
                  className="h-11 rounded-field border-[1.5px] border-field-border bg-surface px-2 text-sm font-semibold"
                >
                  <option value="cents">cént/L</option>
                  <option value="percent">%</option>
                </select>
                <button
                  type="button"
                  aria-label={`Quitar el descuento${d.brand ? ` de ${d.brand}` : ""}`}
                  onClick={() => onChange(discounts.filter((_, j) => j !== i))}
                  className="inline-flex size-11 items-center justify-center rounded-field border-[1.5px] border-rule hover:bg-rule-soft"
                >
                  <CloseIcon size={16} />
                </button>
                {invalid ? (
                  <span className="basis-full text-[13px] text-muted">
                    Como mucho{" "}
                    {d.kind === "cents" ? `${MAX_CENTS} céntimos por litro` : `un ${MAX_PERCENT} %`}.
                  </span>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
      <button
        type="button"
        onClick={() => onChange([...discounts, { brand: "", kind: "cents", value: 0 }])}
        className="inline-flex h-11 items-center gap-1.5 self-start text-[15px] font-bold text-accent hover:text-accent-strong"
      >
        <PlusIcon size={16} /> Añadir un descuento
      </button>
    </div>
  );
}
