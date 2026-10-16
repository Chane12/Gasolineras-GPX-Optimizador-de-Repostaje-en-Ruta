"use client";

import Link from "next/link";
import { useQueryStates } from "nuqs";
import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";

import { Button, buttonClasses } from "@/components/button";
import { FreshnessPill } from "@/components/freshness-pill";
import { WarningIcon } from "@/components/icons";
import { ServerWarmupNotice } from "@/components/server-warmup-notice";
import { StationRow } from "@/components/station-row";
import { api, type ApiClient } from "@/lib/api/client";
import { type RouteSource, routeSourceKey, useRoute, useStationSearch } from "@/lib/api/queries";
import { formatKm } from "@/lib/format";
import { plateTones, stationKey } from "@/lib/map/geo";
import { routeSourceFrom, searchOptionsFrom, searchParams } from "@/lib/search-params";

import { RouteMapLazy } from "./route-map-lazy";

function routeTitle(source: RouteSource): string {
  switch (source.kind) {
    case "text":
      return `${source.origin} → ${source.destination}`;
    case "gpx":
      return "Tu ruta GPX";
    case "demo":
      return "Sierra de Gredos · ejemplo";
  }
}

/** Alto de un elemento, para que el mapa encuadre la ruta en la parte que queda a la vista. */
function useHeight<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [height, setHeight] = useState(0);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    // Alto completo (con relleno y borde): es lo que tapa del mapa.
    const observer = new ResizeObserver(() => setHeight(element.getBoundingClientRect().height));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, height] as const;
}

/**
 * Resultados: mapa a pantalla completa con la ruta y los precios. La lista de abajo es provisional:
 * en el paso 7 del plan pasa a ser la hoja deslizable, y en el 8 las paradas se guardan en el dispositivo.
 */
export function RouteResults({ client = api }: { client?: ApiClient }) {
  const [params] = useQueryStates(searchParams);
  const source = routeSourceFrom(params);
  const options = searchOptionsFrom(params);

  const route = useRoute(source, client);
  const routeForSearch =
    route.data && source ? { key: routeSourceKey(source), track: route.data.track } : null;
  const search = useStationSearch(routeForSearch, options, client);

  const [stops, setStops] = useState<ReadonlySet<string>>(new Set());
  const [focusedKey, setFocusedKey] = useState<string | null>(null);
  const [topRef, topHeight] = useHeight<HTMLDivElement>();
  const [panelRef, panelHeight] = useHeight<HTMLElement>();

  const stations = useMemo(() => search.data?.stations ?? [], [search.data]);
  const tones = useMemo(() => plateTones(stations), [stations]);

  if (!source) {
    return (
      <Centered>
        <p className="m-0">Falta la ruta: vuelve al inicio y escribe origen y destino o sube tu GPX.</p>
        <Link href="/" className={buttonClasses()}>
          Ir al inicio
        </Link>
      </Centered>
    );
  }

  const toggleStop = (key: string) =>
    setStops((current) => {
      const next = new Set(current);
      if (!next.delete(key)) next.add(key);
      return next;
    });

  const error = route.error ?? search.error;
  const retry = () => void (route.isError ? route.refetch() : search.refetch());

  return (
    <div className="relative h-dvh overflow-hidden">
      <div className="absolute inset-0">
        {route.data ? (
          <RouteMapLazy
            track={route.data.track.coordinates}
            stations={stations}
            stopKeys={stops}
            focusedKey={focusedKey}
            onStationSelect={setFocusedKey}
            padding={{ top: topHeight + 12, bottom: panelHeight, left: 0, right: 0 }}
          />
        ) : (
          <div className="size-full bg-map-land" />
        )}
      </div>

      <div ref={topRef} className="absolute inset-x-3 top-3 flex flex-col items-start gap-2">
        <header className="flex w-full items-center gap-3 rounded-card border border-rule bg-surface py-2 pr-2 pl-3.5 shadow-float">
          <RouteGlyph />
          <div className="min-w-0 flex-1">
            <h1 className="m-0 truncate text-[17px] leading-tight font-bold">{routeTitle(source)}</h1>
            <p className="m-0 mt-0.5 font-mono text-xs text-muted">
              {search.data
                ? `${formatKm(search.data.route_km)} km · ${search.data.fuel.label}`
                : route.isPending
                  ? "Calculando la ruta…"
                  : "Buscando gasolineras…"}
            </p>
          </div>
          <Link href="/" className={buttonClasses({ variant: "secondary" })}>
            Editar
          </Link>
        </header>
        {search.data ? (
          <FreshnessPill
            status={search.data.prices.status}
            ageMinutes={search.data.prices.age_minutes ?? null}
          />
        ) : null}
      </div>

      <section
        ref={panelRef}
        aria-labelledby="results-title"
        className="absolute inset-x-0 bottom-0 flex max-h-[45dvh] flex-col gap-3 rounded-t-sheet border-t border-rule bg-surface px-4 pt-4 pb-[max(1rem,env(safe-area-inset-bottom))]"
      >
        <div>
          <p className="m-0 font-mono text-[11px] font-semibold tracking-[0.1em] text-muted">
            GASOLINERAS EN TU RUTA
          </p>
          <h2 id="results-title" className="m-0 mt-0.5 text-2xl leading-tight font-bold tracking-[-0.015em]">
            Elige tus paradas
          </h2>
        </div>

        <ServerWarmupNotice client={client} />

        {error ? (
          <div
            role="alert"
            className="flex items-center gap-3 rounded-card border-[1.5px] border-ink p-3 text-[15px]"
          >
            <WarningIcon size={20} className="shrink-0 text-warn" />
            <span className="flex-1">{error.message}</span>
            <Button variant="secondary" onClick={retry}>
              Reintentar
            </Button>
          </div>
        ) : route.isPending || search.isPending ? (
          <p role="status" className="m-0 text-muted">
            {route.isPending ? "Calculando la ruta…" : "Buscando gasolineras en tu ruta…"}
          </p>
        ) : stations.length === 0 ? (
          <p className="m-0">
            No hay gasolineras con este combustible cerca de la ruta. Prueba a ampliar la distancia máxima.
          </p>
        ) : (
          <ul className="m-0 -mx-1 list-none overflow-y-auto px-1 p-0">
            {stations.map((s, i) => {
              const key = stationKey(s);
              return (
                <StationRow
                  key={key}
                  name={s.name}
                  kmOnRoute={s.km_on_route}
                  price={s.price}
                  town={s.town}
                  schedule={s.open_24h ? "24 h" : null}
                  cheapest={tones[i] === "best"}
                  dimmed={tones[i] === "expensive"}
                  inPlan={stops.has(key)}
                  onTogglePlan={() => toggleStop(key)}
                  onSelect={() => setFocusedKey(key)}
                />
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}

function Centered({ children }: { children: ReactNode }) {
  return <main className="mx-auto flex max-w-xl flex-col items-start gap-4 px-4 py-10">{children}</main>;
}

/** Origen (círculo), trayecto y destino (cuadrado), como en el mapa. */
function RouteGlyph() {
  return (
    <svg width="16" height="40" viewBox="0 0 16 40" aria-hidden="true" className="shrink-0">
      <circle cx="8" cy="7" r="5" fill="none" className="stroke-accent" strokeWidth="2.5" />
      <path d="M8 13v14" className="stroke-muted" strokeWidth="2" strokeDasharray="2 3" />
      <rect x="3" y="28" width="10" height="10" className="fill-accent" />
    </svg>
  );
}
