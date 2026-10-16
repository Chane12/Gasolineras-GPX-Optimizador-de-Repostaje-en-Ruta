import { useEffect, useRef } from "react";

import { ButtonLink } from "@/components/button";
import { Hito } from "@/components/hito";
import { CheckIcon, ChevronLeftIcon, NavigateIcon, PlusIcon, WarningIcon } from "@/components/icons";
import type { DetourInfo } from "@/lib/api/detours";
import { formatAge, formatKm, formatPrice, formatPriceDelta, formatShortKm } from "@/lib/format";
import type { Station } from "@/lib/map/geo";
import { formatSchedule, formatStationName } from "@/lib/stations";

export interface NeighbourStation {
  key: string;
  station: Station;
}

/** Enlace de navegación a la gasolinera en Google Maps (abre la app en el móvil). */
export function directionsUrl(station: Pick<Station, "lat" | "lon">): string {
  return `https://www.google.com/maps/dir/?api=1&destination=${station.lat},${station.lon}&travelmode=driving`;
}

function longSchedule(station: Station): string {
  const short = formatSchedule(station.schedule) ?? (station.open_24h ? "24 h" : null);
  if (!short) return "Sin horario publicado";
  return short === "24 h" ? "Abierta 24 h, todos los días" : short;
}

function detourText(detour: DetourInfo | undefined): string {
  if (!detour || (detour.km === null && detour.attempts < 3)) return "Calculando…";
  if (detour.km === null) return "No disponible ahora";
  const minutes = detour.minutes !== null ? ` · +${Math.max(1, Math.round(detour.minutes))} min` : "";
  return `${formatShortKm(detour.km)} km ida y vuelta${minutes}`;
}

/**
 * Ficha de una gasolinera (maquetas Escritorio-Ficha y Movil-Ficha): sustituye a la lista en el panel o
 * en la hoja. Anterior/siguiente por km para recorrer la ruta sin volver a la lista.
 */
export function StationSheet({
  station,
  detour,
  cheapest,
  inPlan,
  onTogglePlan,
  onBack,
  previous,
  next,
  onNavigate,
  nextRecommended,
  fuelLabel,
  priceAgeMinutes,
  passingNote = null,
}: {
  station: Station;
  detour: DetourInfo | undefined;
  cheapest: boolean;
  inPlan: boolean;
  onTogglePlan: () => void;
  onBack: () => void;
  previous: NeighbourStation | null;
  next: NeighbourStation | null;
  onNavigate: (key: string) => void;
  /** La siguiente recomendada por delante, para saber cuánto queda hasta otra buena opción. */
  nextRecommended: Station | null;
  fuelLabel: string;
  priceAgeMinutes: number | null;
  /** "Abierta al pasar (≈ 14:20)" / "Cerrada al pasar…", si se activó en las opciones avanzadas. */
  passingNote?: { text: string; warn: boolean } | null;
}) {
  const name = formatStationName(station.name);
  const heading = useRef<HTMLHeadingElement>(null);
  // Al abrir otra ficha, el foco va a su título (teclado y lectores de pantalla saben dónde están).
  useEffect(() => {
    heading.current?.focus();
  }, [station]);

  const neighbour = (n: NeighbourStation | null, direction: "prev" | "next") =>
    n ? (
      <button
        type="button"
        onClick={() => onNavigate(n.key)}
        aria-label={`${direction === "prev" ? "Anterior" : "Siguiente"}: ${formatStationName(n.station.name)}, km ${formatKm(n.station.km_on_route)}`}
        className="inline-flex h-11 items-center gap-1.5 rounded-field border-[1.5px] border-rule px-3 text-sm font-semibold hover:bg-rule-soft"
      >
        {direction === "prev" ? "← " : ""}km{" "}
        <span className="font-mono">{formatKm(n.station.km_on_route)}</span>
        {direction === "next" ? " →" : ""}
      </button>
    ) : null;

  return (
    <article aria-labelledby="station-title" className="flex flex-col gap-4">
      <nav aria-label="Navegar entre gasolineras" className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={onBack}
          className="-ml-1 inline-flex h-11 items-center gap-1 px-1 text-[15px] font-bold text-accent hover:text-accent-strong"
        >
          <ChevronLeftIcon size={18} /> Volver a la lista
        </button>
        <div className="flex gap-2">
          {neighbour(previous, "prev")}
          {neighbour(next, "next")}
        </div>
      </nav>

      <div className="flex items-start gap-4">
        <Hito km={station.km_on_route} size="lg" />
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2
              id="station-title"
              ref={heading}
              tabIndex={-1}
              className="m-0 text-[26px] leading-tight font-bold tracking-[-0.015em] outline-none"
            >
              {name}
            </h2>
            {cheapest ? (
              <span className="rounded-[3px] bg-accent px-[5px] pt-0.5 pb-px text-[11px] font-bold tracking-wide text-on-accent">
                MÁS BARATA
              </span>
            ) : null}
          </div>
          <p className="m-0 mt-1 text-[15px] text-muted">
            {[
              station.address ? formatStationName(station.address) : null,
              station.town ? formatStationName(station.town) : null,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
      </div>

      <p className="m-0 flex items-baseline gap-2.5">
        <span className={`font-mono text-[44px] leading-none font-semibold ${cheapest ? "text-accent" : ""}`}>
          {formatPrice(station.price)}
        </span>
        <span className="text-[17px] font-semibold text-muted">€/L · {fuelLabel}</span>
      </p>

      {passingNote ? (
        <p
          className={`m-0 flex items-center gap-1.5 text-[15px] ${passingNote.warn ? "font-semibold" : "text-muted"}`}
        >
          {passingNote.warn ? <WarningIcon size={16} className="shrink-0 text-warn" /> : null}
          {passingNote.text}
        </p>
      ) : null}

      <dl className="m-0 grid grid-cols-2 border-t-2 border-ink">
        {[
          ["Desvío real", detourText(detour)],
          ["Horario", longSchedule(station)],
          [
            "Ahorro frente a la más cara",
            station.savings_vs_max != null ? `${formatPriceDelta(station.savings_vs_max)} €/L` : "—",
          ],
          [
            "Siguiente recomendada",
            nextRecommended
              ? `en ${formatKm(nextRecommended.km_on_route - station.km_on_route)} km (${formatStationName(nextRecommended.name)})`
              : "Ninguna más por delante",
          ],
        ].map(([label, value], index) => (
          <div
            key={label}
            className={`border-b border-rule py-2.5 ${index % 2 === 1 ? "border-l pl-3" : "pr-2"}`}
          >
            <dt className="text-[13px] font-semibold text-muted">{label}</dt>
            <dd className="m-0 mt-0.5 text-base font-semibold">{value}</dd>
          </div>
        ))}
      </dl>

      <div className="flex flex-wrap gap-2.5">
        <button
          type="button"
          aria-pressed={inPlan}
          onClick={onTogglePlan}
          className={`inline-flex h-[52px] flex-[1_1_180px] items-center justify-center gap-2 rounded-button text-base font-bold ${
            inPlan
              ? "bg-accent text-on-accent hover:bg-accent-strong"
              : "border-[1.5px] border-accent text-accent hover:bg-rule-soft"
          }`}
        >
          {inPlan ? <CheckIcon size={18} /> : <PlusIcon size={18} />}
          {inPlan ? "En tus paradas" : "Añadir parada"}
        </button>
        <ButtonLink
          href={directionsUrl(station)}
          target="_blank"
          rel="noopener"
          variant="secondary"
          size="lg"
          className="h-[52px] flex-[1_1_180px]"
        >
          <NavigateIcon size={18} /> Cómo llegar
        </ButtonLink>
      </div>

      <p className="m-0 text-[13px] text-muted">
        {priceAgeMinutes !== null
          ? `Precio publicado en el MITECO hace ${formatAge(priceAgeMinutes)}. `
          : "Precio publicado en el MITECO. "}
        Puede cambiar antes de que llegues.
      </p>
    </article>
  );
}
