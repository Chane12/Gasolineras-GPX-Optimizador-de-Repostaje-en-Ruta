import Link from "next/link";

import { ChevronRightIcon } from "@/components/icons";
import { formatKm } from "@/lib/format";

export interface RouteStop {
  key: string;
  kmOnRoute: number;
}

function listKms(stops: readonly RouteStop[]): string {
  const kms = stops.map((s) => `km ${formatKm(s.kmOnRoute)}`);
  if (kms.length <= 1) return kms.join("");
  return `${kms.slice(0, -1).join(", ")} y ${kms.at(-1)}`;
}

/**
 * "Tu ruta" (maquetas Escritorio-Ruta y Movil-Resultados): las paradas elegidas sobre el trayecto, siempre a
 * la vista. En tinta, como la barra del diseño. Con alguna parada, da paso a la hoja de ruta.
 */
export function TuRutaBar({
  stops,
  routeKm,
  planHref,
}: {
  stops: readonly RouteStop[];
  routeKm: number;
  /** Enlace a la hoja de ruta (con la búsqueda y las paradas): aparece en cuanto hay una parada. */
  planHref?: string;
}) {
  const sorted = [...stops].sort((a, b) => a.kmOnRoute - b.kmOnRoute);
  return (
    <section
      aria-label="Tu ruta"
      className="flex items-center gap-3.5 rounded-card bg-ink px-4 py-3 text-bg shadow-bar"
    >
      <div className="flex min-w-0 flex-1 flex-col gap-2.5" aria-live="polite">
        <div className="flex items-baseline justify-between gap-3">
          <span className="text-base font-bold">Tu ruta</span>
          <span className="truncate text-[13px] opacity-80">
            {sorted.length === 0 ? (
              "Añade tus paradas con +"
            ) : (
              <>
                <span className="font-mono">{sorted.length}</span>{" "}
                {sorted.length === 1 ? "parada" : "paradas"} · {listKms(sorted)}
              </>
            )}
          </span>
        </div>
        <div className="relative h-[18px]" aria-hidden="true">
          <div className="absolute inset-x-1.5 top-2 h-0.5 bg-muted" />
          <span className="absolute top-[3px] left-0 size-3 rounded-full border-[3px] border-bg bg-ink" />
          {sorted.map((stop) => (
            <span
              key={stop.key}
              className="absolute top-0 h-4 w-3 overflow-hidden rounded-t-[6px] rounded-b-[1px] bg-hito-body"
              style={{
                left: `calc(${Math.min(100, Math.max(0, (stop.kmOnRoute / (routeKm || 1)) * 100))}% - 6px)`,
              }}
            >
              <span className="block h-[5px] bg-hito-red" />
            </span>
          ))}
          <span className="absolute top-[3px] right-0 size-3 bg-bg" />
        </div>
      </div>
      {planHref && sorted.length > 0 ? (
        <Link
          href={planHref}
          className="inline-flex h-11 shrink-0 items-center gap-1.5 rounded-field bg-bg px-3.5 text-[15px] font-bold text-ink no-underline hover:text-ink"
        >
          Hoja de ruta <ChevronRightIcon size={16} />
        </Link>
      ) : null}
    </section>
  );
}
