"use client";

import { type ReactNode, useEffect, useId, useState } from "react";

import { ChevronDownIcon } from "@/components/icons";

const STORAGE_KEY = "gasolineras:avanzadas-abiertas";

/**
 * "Opciones avanzadas" (punto 10): plegadas por defecto, para quien las quiera. Se recuerda en el
 * dispositivo si se dejaron abiertas, y `active` dice cuántas hay en uso aunque estén plegadas.
 */
export function AdvancedOptions({ active = 0, children }: { active?: number; children: ReactNode }) {
  const ids = useId();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    try {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- leer el dispositivo solo es posible tras montar
      setOpen(localStorage.getItem(STORAGE_KEY) === "1");
    } catch {
      // Sin almacenamiento: plegadas.
    }
  }, []);

  function toggle() {
    setOpen((o) => {
      try {
        localStorage.setItem(STORAGE_KEY, o ? "0" : "1");
      } catch {
        // Nada que guardar.
      }
      return !o;
    });
  }

  return (
    <section className="border-y border-rule">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={`${ids}-panel`}
        onClick={toggle}
        className="flex min-h-12 w-full items-center justify-between gap-3 py-1.5 text-left"
      >
        <span className="flex items-center gap-2">
          <span className="text-[15px] font-bold">Opciones avanzadas</span>
          {active > 0 ? (
            <span className="rounded-[3px] border-[1.5px] border-accent px-1.5 text-xs font-bold text-accent">
              {active} {active === 1 ? "activa" : "activas"}
            </span>
          ) : null}
        </span>
        <ChevronDownIcon size={18} className={`shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {/* Solo se pinta abierto: lo que hay dentro puede leer ajustes del dispositivo. */}
      {open ? (
        <div id={`${ids}-panel`} className="flex flex-col gap-6 pt-2 pb-5">
          {children}
        </div>
      ) : null}
    </section>
  );
}
