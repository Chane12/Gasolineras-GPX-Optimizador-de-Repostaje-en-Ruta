"use client";

import { useId } from "react";

import type { PassingSettings } from "@/lib/use-passing-time";

/** Controles de "Abierta cuando pases" (punto 10b), dentro de las opciones avanzadas. */
export function PassingTimeOptions({
  settings,
  onChange,
  routeSpeedKmh = null,
}: {
  settings: PassingSettings;
  onChange: (next: Partial<PassingSettings>) => void;
  /** Media de la ruta calculada (sin paradas), para proponerla; null en rutas GPX. */
  routeSpeedKmh?: number | null;
}) {
  const ids = useId();
  return (
    <div className="flex flex-col gap-3">
      <div>
        <h3 className="m-0 text-[17px] font-bold">Abierta cuando pases</h3>
        <p className="m-0 mt-0.5 text-sm text-muted">
          Con tu hora de salida, te avisamos de las que estarán cerradas cuando llegues a ellas.
        </p>
      </div>
      <label className="flex min-h-11 items-center gap-3 text-[15px]">
        <input
          type="checkbox"
          className="size-5 shrink-0 accent-accent"
          checked={settings.enabled}
          onChange={(e) => onChange({ enabled: e.target.checked })}
        />
        Tener en cuenta la hora a la que paso
      </label>
      {settings.enabled ? (
        <div className="flex flex-col gap-3 pl-8">
          <div className="flex flex-wrap gap-x-5 gap-y-3">
            <label className="flex flex-col gap-1 text-sm font-bold" htmlFor={`${ids}-dep`}>
              Salgo el
              <input
                id={`${ids}-dep`}
                type="datetime-local"
                value={settings.departure}
                onChange={(e) => e.target.value && onChange({ departure: e.target.value })}
                className="h-11 rounded-field border-[1.5px] border-field-border bg-surface px-3 font-mono text-sm font-semibold text-ink"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm font-bold" htmlFor={`${ids}-speed`}>
              Velocidad media
              <span className="flex items-center gap-2 font-semibold">
                <input
                  id={`${ids}-speed`}
                  inputMode="numeric"
                  value={settings.speedKmh || ""}
                  onChange={(e) => onChange({ speedKmh: Number(e.target.value.replace(/\D/g, "")) || 0 })}
                  aria-describedby={`${ids}-speed-hint`}
                  className="h-11 w-20 rounded-field border-[1.5px] border-field-border bg-surface px-3 font-mono text-sm"
                />
                km/h
              </span>
            </label>
          </div>
          <p id={`${ids}-speed-hint`} className="m-0 text-[13px] text-muted">
            {routeSpeedKmh !== null
              ? `Esta ruta sale a unos ${routeSpeedKmh} km/h de media sin contar paradas.`
              : "Contando paradas: por autovía, unos 90 km/h; por carreteras de montaña, 50–60."}
          </p>
          {routeSpeedKmh !== null && settings.speedKmh !== routeSpeedKmh ? (
            <button
              type="button"
              onClick={() => onChange({ speedKmh: routeSpeedKmh })}
              className="-mt-1.5 min-h-11 self-start text-sm font-semibold text-accent underline underline-offset-2"
            >
              Usar {routeSpeedKmh} km/h
            </button>
          ) : null}
          <label className="flex min-h-11 items-center gap-3 text-[15px]">
            <input
              type="checkbox"
              className="size-5 shrink-0 accent-accent"
              checked={settings.hideClosed}
              onChange={(e) => onChange({ hideClosed: e.target.checked })}
            />
            Ocultar las que estarán cerradas
          </label>
          <p className="m-0 text-[13px] text-muted">
            Según el horario publicado en el MITECO; los festivos no aparecen en él.
          </p>
        </div>
      ) : null}
    </div>
  );
}
