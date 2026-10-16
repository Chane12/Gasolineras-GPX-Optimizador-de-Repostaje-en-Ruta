"use client";

import { useEffect, useId, useState } from "react";

import { Button } from "@/components/button";
import { Hito } from "@/components/hito";
import { WarningIcon } from "@/components/icons";
import { formatKm, formatPrice } from "@/lib/format";
import { type Station, stationKey } from "@/lib/map/geo";
import { type PlanMode, planRefuels, type RefuelPlan } from "@/lib/refuel-plan";
import { LIMITS } from "@/lib/search-params";
import { formatStationName } from "@/lib/stations";

const STORAGE_KEY = "gasolineras:planificador";
const START_CHOICES = [
  { value: 1, label: "Lleno" },
  { value: 0.75, label: "3/4" },
  { value: 0.5, label: "Medio" },
  { value: 0.25, label: "1/4" },
] as const;
const PROFILES = [
  { label: "Moto", km: 250 },
  { label: "Coche", km: 600 },
  { label: "Gran autonomía", km: 900 },
] as const;
/** Gasolineras con un desvío conocido mayor que esto no entran en el plan. */
const MAX_DETOUR_KM = 8;

interface Settings {
  autonomyKm: number;
  startFraction: number;
  reserveKm: number;
  mode: PlanMode;
}

function loadSettings(fallbackAutonomy: number): Settings {
  const defaults: Settings = {
    autonomyKm: fallbackAutonomy,
    startFraction: 1,
    reserveKm: Math.round(fallbackAutonomy * 0.15),
    mode: "cheapest",
  };
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null") as Partial<Settings> | null;
    return saved ? { ...defaults, ...saved } : defaults;
  } catch {
    return defaults;
  }
}

function fillText(fill: number, full: boolean): string {
  if (full) return "Llena el depósito";
  const percent = Math.max(5, Math.round((fill * 100) / 5) * 5);
  return `Echa ~${percent} % del depósito`;
}

const chip = "h-10 rounded-field border-[1.5px] px-3 text-sm font-semibold";
const chipOn = "border-accent text-accent";
const chipOff = "border-field-border hover:bg-rule-soft";

/**
 * Planificar mis repostajes (punto 10a): con la autonomía, con cuánto se sale y la reserva, propone dónde
 * parar y cuánto echar para no bajar nunca de la reserva. "Lo más barato" es el plan óptimo; "Menos
 * paradas" para solo cuando hace falta. Las paradas propuestas pasan a "Tu ruta" con un botón.
 */
export function RefuelPlanner({
  stations,
  routeKm,
  detourKm,
  defaultAutonomyKm,
  onUse,
  exclude,
}: {
  stations: readonly Station[];
  routeKm: number;
  /** Desvío conocido de cada gasolinera (las de desvíos grandes no entran en el plan). */
  detourKm: (key: string) => number | null;
  defaultAutonomyKm: number;
  onUse: (keys: string[]) => void;
  /** Gasolineras que no deben entrar en el plan (p. ej. cerradas cuando se pase por ellas). */
  exclude?: (key: string) => boolean;
}) {
  const ids = useId();
  const [settings, setSettings] = useState<Settings>(() => loadSettings(defaultAutonomyKm || 250));
  const [plan, setPlan] = useState<RefuelPlan | null>(null);
  /** El plan con el otro modo, para comparar ("Con «Menos paradas» serían…"). */
  const [alternative, setAlternative] = useState<RefuelPlan | null>(null);
  const [used, setUsed] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    } catch {
      // Sin almacenamiento: los ajustes duran lo que la página.
    }
  }, [settings]);

  const update = (next: Partial<Settings>) => {
    setSettings((s) => ({ ...s, ...next }));
    setPlan(null);
    setUsed(false);
  };
  const autonomyValid =
    settings.autonomyKm >= LIMITS.autonomiaKm.min && settings.autonomyKm <= LIMITS.autonomiaKm.max;
  const reserveValid = settings.reserveKm >= 0 && settings.reserveKm < settings.autonomyKm;

  function propose() {
    const candidates = stations
      .filter((s) => (detourKm(stationKey(s)) ?? 0) <= MAX_DETOUR_KM && !exclude?.(stationKey(s)))
      .map((s) => ({ key: stationKey(s), km: s.km_on_route, price: s.price }));
    setPlan(planRefuels(candidates, routeKm, settings));
    setAlternative(
      planRefuels(candidates, routeKm, {
        ...settings,
        mode: settings.mode === "cheapest" ? "fewest" : "cheapest",
      }),
    );
    setUsed(false);
  }

  const byKey = new Map(stations.map((s) => [stationKey(s), s]));
  const routeAverage =
    stations.length > 0 ? stations.reduce((sum, s) => sum + s.price, 0) / stations.length : null;

  return (
    <div className="flex flex-col gap-3.5">
      <div>
        <h3 className="m-0 text-[17px] font-bold">Planificar mis repostajes</h3>
        <p className="m-0 mt-0.5 text-sm text-muted">
          Te proponemos dónde parar y cuánto echar para no bajar nunca de tu reserva.
        </p>
      </div>

      <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
        <legend className="mb-1.5 text-sm font-bold">Autonomía con el depósito lleno</legend>
        <div className="flex flex-wrap items-center gap-2">
          {PROFILES.map((p) => (
            <button
              key={p.km}
              type="button"
              aria-pressed={settings.autonomyKm === p.km}
              onClick={() => update({ autonomyKm: p.km, reserveKm: Math.round(p.km * 0.15) })}
              className={`${chip} ${settings.autonomyKm === p.km ? chipOn : chipOff}`}
            >
              {p.label} · <span className="font-mono">{p.km}</span> km
            </button>
          ))}
          <label className="flex items-center gap-2 text-sm font-semibold">
            <span className="sr-only">Autonomía en km</span>
            <input
              inputMode="numeric"
              value={settings.autonomyKm || ""}
              onChange={(e) => update({ autonomyKm: Number(e.target.value.replace(/\D/g, "")) || 0 })}
              aria-invalid={!autonomyValid || undefined}
              className="h-10 w-24 rounded-field border-[1.5px] border-field-border bg-surface px-3 font-mono text-sm"
            />
            km
          </label>
        </div>
      </fieldset>

      <div className="flex flex-wrap gap-x-6 gap-y-3">
        <fieldset className="m-0 border-0 p-0">
          <legend className="mb-1.5 text-sm font-bold">Sales con</legend>
          <div className="flex gap-1.5">
            {START_CHOICES.map((c) => (
              <button
                key={c.value}
                type="button"
                aria-pressed={settings.startFraction === c.value}
                onClick={() => update({ startFraction: c.value })}
                className={`${chip} ${settings.startFraction === c.value ? chipOn : chipOff}`}
              >
                {c.label}
              </button>
            ))}
          </div>
        </fieldset>
        <label className="flex flex-col gap-1.5 text-sm font-bold" htmlFor={`${ids}-reserve`}>
          Reserva mínima
          <span className="flex items-center gap-2 font-semibold">
            <input
              id={`${ids}-reserve`}
              inputMode="numeric"
              value={settings.reserveKm}
              onChange={(e) => update({ reserveKm: Number(e.target.value.replace(/\D/g, "")) || 0 })}
              aria-invalid={!reserveValid || undefined}
              className="h-10 w-20 rounded-field border-[1.5px] border-field-border bg-surface px-3 font-mono text-sm"
            />
            km
          </span>
        </label>
      </div>

      <fieldset className="m-0 border-0 p-0">
        <legend className="mb-1.5 text-sm font-bold">Prefiero</legend>
        <div className="flex flex-wrap gap-1.5">
          {(
            [
              ["cheapest", "Lo más barato"],
              ["fewest", "Menos paradas"],
            ] as const
          ).map(([mode, label]) => (
            <button
              key={mode}
              type="button"
              aria-pressed={settings.mode === mode}
              onClick={() => update({ mode })}
              className={`${chip} ${settings.mode === mode ? chipOn : chipOff}`}
            >
              {label}
            </button>
          ))}
        </div>
      </fieldset>

      <Button
        variant="secondary"
        onClick={propose}
        disabled={!autonomyValid || !reserveValid || stations.length === 0}
      >
        Proponer paradas
      </Button>
      {!autonomyValid ? (
        <p className="m-0 text-sm text-muted">
          Indica una autonomía entre {LIMITS.autonomiaKm.min} y {LIMITS.autonomiaKm.max} km.
        </p>
      ) : null}

      {plan?.status === "impossible" ? (
        <p role="alert" className="m-0 flex items-start gap-2 text-[15px]">
          <WarningIcon size={18} className="mt-0.5 shrink-0 text-warn" />
          {plan.reason === "start-below-reserve"
            ? "Sales con menos combustible que tu reserva: reposta antes de salir o baja la reserva."
            : `Con esa autonomía no llegas: del km ${formatKm(plan.fromKm)} al ${formatKm(plan.toKm)} no hay ninguna gasolinera a tu alcance. Prueba a ampliar el desvío o a salir con más.`}
        </p>
      ) : null}

      {plan?.status === "ok" ? (
        <div className="flex flex-col gap-2.5" aria-live="polite">
          {plan.stops.length === 0 ? (
            <p className="m-0 text-[15px]">Con lo que llevas llegas sin repostar (y con tu reserva).</p>
          ) : (
            <>
              <p className="m-0 text-[15px]">
                <b>
                  {plan.stops.length} {plan.stops.length === 1 ? "parada" : "paradas"}
                </b>
                {plan.averagePrice !== null ? (
                  <>
                    {" "}
                    · pagarás de media{" "}
                    <span className="font-mono font-semibold">{formatPrice(plan.averagePrice)}</span> €/L
                    {routeAverage !== null ? (
                      <span className="text-muted">
                        {" "}
                        (media de la ruta: <span className="font-mono">{formatPrice(routeAverage)}</span>)
                      </span>
                    ) : null}
                  </>
                ) : null}
              </p>
              <ol className="m-0 flex list-none flex-col p-0" aria-label="Paradas propuestas">
                {plan.stops.map((stop) => {
                  const station = byKey.get(stop.key);
                  return (
                    <li key={stop.key} className="flex items-center gap-3 border-b border-rule-soft py-2">
                      <Hito km={stop.km} size="sm" />
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-bold">
                          {station ? formatStationName(station.name) : stop.key}
                          {station?.town ? (
                            <span className="font-normal text-muted">
                              {" "}
                              · {formatStationName(station.town)}
                            </span>
                          ) : null}
                        </div>
                        <div className="text-sm text-muted">{fillText(stop.fill, stop.full)}</div>
                      </div>
                      <span className="font-mono text-base font-semibold">{formatPrice(stop.price)}</span>
                    </li>
                  );
                })}
              </ol>
              {alternative?.status === "ok" && alternative.stops.length !== plan.stops.length ? (
                <p className="m-0 text-sm text-muted">
                  Con «{settings.mode === "cheapest" ? "Menos paradas" : "Lo más barato"}» serían{" "}
                  {alternative.stops.length} {alternative.stops.length === 1 ? "parada" : "paradas"}
                  {alternative.averagePrice !== null ? (
                    <>
                      {" "}
                      (media <span className="font-mono">{formatPrice(alternative.averagePrice)}</span> €/L)
                    </>
                  ) : null}
                  .
                </p>
              ) : null}
              <Button
                onClick={() => {
                  onUse(plan.stops.map((s) => s.key));
                  setUsed(true);
                }}
                disabled={used}
              >
                {used ? "Ya están en «Tu ruta»" : "Usar estas paradas"}
              </Button>
            </>
          )}
          <p className="m-0 text-[13px] text-muted">
            Es una estimación con la autonomía que indicas: tu consumo real depende de cómo y por dónde
            conduzcas.
          </p>
        </div>
      ) : null}
    </div>
  );
}
