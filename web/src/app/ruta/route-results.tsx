"use client";

import Link from "next/link";
import { parseAsString, useQueryState } from "nuqs";
import {
  type PointerEvent,
  type ReactNode,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";

import { AutonomyWarnings } from "@/components/autonomy-warnings";
import { Button, buttonClasses } from "@/components/button";
import { FilterBar, type Filters } from "@/components/filter-bar";
import { FreshnessPill } from "@/components/freshness-pill";
import { CloseIcon, WarningIcon } from "@/components/icons";
import { RouteSearchBar } from "@/components/route-search-bar";
import { Logo } from "@/components/site-header";
import { ServerWarmupNotice } from "@/components/server-warmup-notice";
import { StationRow } from "@/components/station-row";
import { StationSheet } from "@/components/station-sheet";
import { SummaryStats } from "@/components/summary-stats";
import { TuRutaBar } from "@/components/tu-ruta-bar";
import { api, type ApiClient } from "@/lib/api/client";
import { useDetours } from "@/lib/api/detours";
import { type RouteSource, routeSourceKey } from "@/lib/api/queries";
import { formatKm, formatPrice, formatPriceDelta } from "@/lib/format";
import { plateTones, type Station, stationKey } from "@/lib/map/geo";
import { normalizeOptions, serializeSearch } from "@/lib/search-params";
import { formatSchedule, formatStationName } from "@/lib/stations";
import { placeValueFrom } from "@/lib/use-place-check";

import { RouteMapLazy } from "./route-map-lazy";
import { useRouteData } from "./use-route-data";

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

const DESKTOP = "(min-width: 1024px)";

/** ¿Pantalla de ordenador? (Solo para el encuadre del mapa: la disposición la decide el CSS.) */
function useIsDesktop(): boolean {
  return useSyncExternalStore(
    (notify) => {
      const query = window.matchMedia(DESKTOP);
      query.addEventListener("change", notify);
      return () => query.removeEventListener("change", notify);
    },
    () => window.matchMedia(DESKTOP).matches,
    () => false,
  );
}

/** Alto de un elemento (con relleno y borde), para que el mapa encuadre la ruta en lo que queda a la vista. */
function useHeight<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [height, setHeight] = useState(0);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new ResizeObserver(() => setHeight(element.getBoundingClientRect().height));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, height] as const;
}

type Snap = "peek" | "half" | "full";
const SNAPS: Snap[] = ["peek", "half", "full"];
/** Alto de la hoja del móvil en cada posición (px a partir del alto de la ventana). */
function snapHeight(snap: Snap, viewport: number): number {
  if (snap === "peek") return 228;
  if (snap === "half") return Math.round(viewport * 0.55);
  return viewport - 88;
}

type Sort = "km" | "price" | "detour";

/**
 * La ruta como sitio de trabajo (maquetas Escritorio-Ruta y Movil-Resultados): búsqueda editable, filtros,
 * resumen, recomendadas (unas 8) y el resto bajo "Ver las N", y "Tu ruta" siempre a la vista.
 * En el ordenador, panel a la izquierda y mapa a la derecha; en el móvil, mapa con una hoja deslizable.
 */
export function RouteResults({ client = api }: { client?: ApiClient }) {
  const { params, setParams, source, route, routeKm, routeForSearch, search, recommended, others, stops } =
    useRouteData(client);
  const isDesktop = useIsDesktop();

  // La ficha abierta va en la URL: "atrás" vuelve a la lista y el enlace se puede compartir.
  const [selectedKey, setSelectedKey] = useQueryState(
    "gasolinera",
    parseAsString.withOptions({ history: "push" }),
  );
  const [focusedKey, setFocusedKey] = useState<string | null>(null);
  const [highlightedKey, setHighlightedKey] = useState<string | null>(null);
  const [sort, setSort] = useState<Sort>("km");
  const [showAll, setShowAll] = useState(false);
  const [snap, setSnap] = useState<Snap>("half");
  const [dragHeight, setDragHeight] = useState<number | null>(null);
  const [viewport, setViewport] = useState(800);
  const [topRef, topHeight] = useHeight<HTMLDivElement>();
  const [panelRef, panelHeight] = useHeight<HTMLElement>();
  const searchDialog = useRef<HTMLDialogElement>(null);
  const [searchOpen, setSearchOpen] = useState(false);

  useEffect(() => {
    const dialog = searchDialog.current;
    if (!dialog) return;
    if (searchOpen && !dialog.open) dialog.showModal();
    if (!searchOpen && dialog.open) dialog.close();
  }, [searchOpen]);

  useEffect(() => {
    const update = () => setViewport(window.innerHeight);
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  const total = recommended.length + others.length;
  const selected = useMemo(
    () =>
      selectedKey ? ([...recommended, ...others].find((s) => stationKey(s) === selectedKey) ?? null) : null,
    [selectedKey, recommended, others],
  );

  // Desvíos reales, en segundo plano: de las recomendadas, las paradas y la ficha abierta.
  const detourTargets = useMemo(() => {
    const byKey = new Map(recommended.map((s) => [stationKey(s), s]));
    for (const s of [...stops.list, ...(selected ? [selected] : [])]) byKey.set(stationKey(s), s);
    return [...byKey.values()];
  }, [recommended, stops, selected]);
  const detours = useDetours(routeForSearch, detourTargets, client);

  const shown = useMemo(() => {
    const list = showAll ? [...recommended, ...others] : [...recommended];
    const detourOf = (s: Station) => detours.get(stationKey(s))?.km ?? Number.POSITIVE_INFINITY;
    return list.sort((a, b) =>
      sort === "km"
        ? a.km_on_route - b.km_on_route
        : sort === "price"
          ? a.price - b.price
          : detourOf(a) - detourOf(b) || a.km_on_route - b.km_on_route,
    );
  }, [recommended, others, showAll, sort, detours]);
  const tones = useMemo(() => plateTones(shown), [shown]);

  // En el mapa llevan placa las recomendadas y, aunque no lo sean, las paradas y la elegida; el resto, punto.
  const [mapPlates, mapDots] = useMemo(() => {
    const withPlate = new Set([...stops.keys, ...[focusedKey, selectedKey].filter((k): k is string => !!k)]);
    const promoted = others.filter((s) => withPlate.has(stationKey(s)));
    return [[...recommended, ...promoted], others.filter((s) => !withPlate.has(stationKey(s)))];
  }, [recommended, others, stops, focusedKey, selectedKey]);

  if (!source) {
    return (
      <main className="mx-auto flex max-w-xl flex-col items-start gap-4 px-4 py-10">
        <p className="m-0">Falta la ruta: vuelve al inicio y escribe origen y destino o sube tu GPX.</p>
        <Link href="/" className={buttonClasses()}>
          Ir al inicio
        </Link>
      </main>
    );
  }

  const toggleStop = stops.toggle;

  const normalized = normalizeOptions(params);
  const filters: Filters = {
    radio: normalized.radio,
    abierta24h: params.abierta24h,
    vaciada: params.vaciada,
    autonomia: normalized.autonomia,
  };

  const searchBar = (layout: "row" | "column", onDone?: () => void) => (
    <RouteSearchBar
      key={`${layout}-${routeSourceKey(source)}`}
      layout={layout}
      places={
        source.kind === "text"
          ? {
              origen: placeValueFrom(params.origen, params.origenGeo),
              destino: placeValueFrom(params.destino, params.destinoGeo),
            }
          : null
      }
      routeName={routeTitle(source)}
      fuel={params.combustible}
      onFuelChange={(combustible) => {
        void setParams({ combustible });
        onDone?.();
      }}
      onSearch={({ origen, destino }) => {
        void setParams({
          origen: origen.text,
          destino: destino.text,
          origenGeo: origen.point ?? null,
          destinoGeo: destino.point ?? null,
          gpx: false,
          demo: false,
          paradas: null,
        });
        onDone?.();
      }}
      client={client}
    />
  );

  function openStation(key: string) {
    void setSelectedKey(key);
    setFocusedKey(key);
    if (!isDesktop) setSnap("half");
  }

  const byKm = [...shown].sort((a, b) => a.km_on_route - b.km_on_route);
  const selectedIndex = selected ? byKm.findIndex((s) => stationKey(s) === stationKey(selected)) : -1;
  const neighbourAt = (i: number) => {
    const station = byKm[i];
    return station ? { key: stationKey(station), station } : null;
  };

  const error = route.error ?? search.error;
  const retry = () => void (route.isError ? route.refetch() : search.refetch());
  const best = recommended.length > 0 ? Math.min(...recommended.map((s) => s.price)) : null;
  const maxPrice = search.data?.max_price_in_corridor ?? null;

  const sheetHeight = dragHeight ?? snapHeight(snap, viewport);

  function onHandlePointerDown(event: PointerEvent<HTMLButtonElement>) {
    const startY = event.clientY;
    const startHeight = sheetHeight;
    let moved = false;
    const target = event.currentTarget;
    target.setPointerCapture(event.pointerId);
    const move = (e: globalThis.PointerEvent) => {
      if (Math.abs(e.clientY - startY) > 4) moved = true;
      if (moved) setDragHeight(Math.min(viewport - 60, Math.max(160, startHeight + (startY - e.clientY))));
    };
    const up = (e: globalThis.PointerEvent) => {
      target.removeEventListener("pointermove", move);
      target.removeEventListener("pointerup", up);
      if (!moved) return;
      const final = Math.min(viewport - 60, Math.max(160, startHeight + (startY - e.clientY)));
      const nearest = SNAPS.reduce((a, b) =>
        Math.abs(snapHeight(a, viewport) - final) <= Math.abs(snapHeight(b, viewport) - final) ? a : b,
      );
      setSnap(nearest);
      setDragHeight(null);
      // El clic que sigue al arrastre no debe cambiar otra vez de posición.
      target.dataset.dragged = "true";
    };
    target.addEventListener("pointermove", move);
    target.addEventListener("pointerup", up);
  }

  const routeSummary = search.data
    ? `${formatKm(search.data.route_km)} km · ${search.data.fuel.label}`
    : route.isPending
      ? "Calculando la ruta…"
      : route.isError
        ? "No se pudo calcular la ruta"
        : "Buscando gasolineras…";

  return (
    <div className="flex h-dvh flex-col overflow-hidden">
      <h1 className="sr-only">{routeTitle(source)}</h1>
      {/* Cabecera del ordenador: logo, búsqueda editable y frescura de los precios. */}
      <header className="hidden items-start gap-5 border-b border-rule px-5 py-2.5 lg:flex">
        <Link
          href="/"
          className="mt-2 shrink-0 text-ink no-underline"
          aria-label="Gasolineras en Ruta, inicio"
        >
          <Logo />
        </Link>
        {searchBar("row")}
        {search.data ? (
          <div className="mt-2 shrink-0">
            <FreshnessPill
              status={search.data.prices.status}
              ageMinutes={search.data.prices.age_minutes ?? null}
            />
          </div>
        ) : null}
      </header>

      <div className="relative flex min-h-0 flex-1">
        <section
          ref={panelRef}
          aria-labelledby="results-title"
          style={{ ["--sheet-h" as string]: `${sheetHeight}px` }}
          className={`absolute inset-x-0 bottom-0 z-10 flex h-[var(--sheet-h)] flex-col rounded-t-sheet border-t border-rule bg-surface shadow-[0_-6px_22px_rgb(var(--shadow-color)/0.10)] lg:static lg:z-auto lg:h-auto lg:w-[480px] lg:shrink-0 lg:rounded-none lg:border-t-0 lg:border-r lg:shadow-none xl:w-[520px] ${
            dragHeight === null ? "transition-[height] duration-200 motion-reduce:transition-none" : ""
          }`}
        >
          <button
            type="button"
            aria-label={snap === "full" ? "Reducir la lista" : "Ampliar la lista"}
            className="mx-auto flex h-6 w-20 shrink-0 cursor-grab touch-none items-center justify-center lg:hidden"
            onPointerDown={onHandlePointerDown}
            onClick={(e) => {
              if (e.currentTarget.dataset.dragged) {
                delete e.currentTarget.dataset.dragged;
                return;
              }
              setSnap((s) => SNAPS[(SNAPS.indexOf(s) + 1) % SNAPS.length] ?? "half");
            }}
          >
            <span className="block h-[5px] w-10 rounded-full bg-field-border" />
          </button>

          <div className="flex min-h-0 flex-1 flex-col gap-3.5 overflow-y-auto px-4 pb-4 lg:px-6 lg:pt-5">
            {selected && search.data ? (
              <StationSheet
                station={selected}
                detour={detours.get(stationKey(selected))}
                cheapest={best !== null && selected.price === best}
                inPlan={stops.keys.has(stationKey(selected))}
                onTogglePlan={() => toggleStop(selected)}
                onBack={() => void setSelectedKey(null)}
                previous={selectedIndex > 0 ? neighbourAt(selectedIndex - 1) : null}
                next={selectedIndex >= 0 ? neighbourAt(selectedIndex + 1) : null}
                onNavigate={openStation}
                nextRecommended={
                  recommended
                    .filter((s) => s.km_on_route > selected.km_on_route + 0.5)
                    .sort((a, b) => a.km_on_route - b.km_on_route)[0] ?? null
                }
                fuelLabel={search.data.fuel.label}
                priceAgeMinutes={search.data.prices.age_minutes ?? null}
              />
            ) : (
              <>
                <div className="flex items-end justify-between gap-3">
                  <div className="min-w-0">
                    <p className="m-0 truncate font-mono text-[11px] font-semibold tracking-[0.1em] text-muted uppercase">
                      {search.data
                        ? `${routeTitle(source)} · ${formatKm(search.data.route_km)} km`
                        : "Gasolineras en tu ruta"}
                    </p>
                    <h2
                      id="results-title"
                      className="m-0 mt-0.5 text-2xl leading-tight font-bold tracking-[-0.015em]"
                    >
                      Elige tus paradas
                    </h2>
                  </div>
                  {search.isFetching && search.data ? (
                    <span role="status" className="shrink-0 pb-1 text-sm text-muted">
                      Actualizando…
                    </span>
                  ) : null}
                </div>

                <ServerWarmupNotice client={client} />

                {route.data ? (
                  <FilterBar
                    filters={filters}
                    onChange={(next) => {
                      void setParams(next);
                      setShowAll(false);
                    }}
                  />
                ) : null}

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
                ) : route.isPending || (search.isPending && !search.data) ? (
                  <p role="status" className="m-0 text-muted">
                    {route.isPending ? "Calculando la ruta…" : "Buscando gasolineras en tu ruta…"}
                  </p>
                ) : total === 0 ? (
                  <p className="m-0">
                    No hay gasolineras con este combustible a menos de {filters.radio} km de la ruta. Prueba a
                    ampliar el desvío{filters.abierta24h ? " o a quitar «Solo abiertas 24 h»" : ""}.
                  </p>
                ) : (
                  <>
                    {search.data?.autonomy && filters.autonomia > 0 ? (
                      <AutonomyWarnings segments={search.data.autonomy} autonomyKm={filters.autonomia} />
                    ) : null}
                    <SummaryStats
                      stats={[
                        {
                          label: "Recomendadas",
                          value: (
                            <>
                              {recommended.length}
                              <span className="text-xs text-muted"> de {total}</span>
                            </>
                          ),
                        },
                        {
                          label: "Mejor precio",
                          accent: true,
                          value: best !== null ? <PriceValue>{formatPrice(best)}</PriceValue> : "—",
                        },
                        {
                          label: "Ahorro hasta",
                          value:
                            best !== null && maxPrice !== null ? (
                              <PriceValue>{formatPriceDelta(maxPrice - best)}</PriceValue>
                            ) : (
                              "—"
                            ),
                        },
                      ]}
                    />
                    <div role="group" aria-label="Ordenar" className="flex gap-5">
                      {(
                        [
                          ["km", "Por km"],
                          ["price", "Por precio"],
                          ["detour", "Por desvío"],
                        ] as const
                      ).map(([value, label]) => (
                        <button
                          key={value}
                          type="button"
                          aria-pressed={sort === value}
                          onClick={() => setSort(value)}
                          className={`h-9 border-b-[2.5px] text-[15px] ${
                            sort === value
                              ? "border-accent font-bold text-accent"
                              : "border-transparent font-semibold text-muted"
                          }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                    <ul
                      className="m-0 list-none p-0"
                      aria-label={showAll ? "Todas las gasolineras" : "Gasolineras recomendadas"}
                    >
                      {shown.map((s, i) => {
                        const key = stationKey(s);
                        const name = formatStationName(s.name);
                        return (
                          <StationRow
                            key={key}
                            name={name}
                            kmOnRoute={s.km_on_route}
                            price={s.price}
                            town={s.town ? formatStationName(s.town) : null}
                            schedule={formatSchedule(s.schedule) ?? (s.open_24h ? "24 h" : null)}
                            detourKm={detours.get(key)?.km ?? null}
                            cheapest={tones[i] === "best"}
                            dimmed={tones[i] === "expensive"}
                            inPlan={stops.keys.has(key)}
                            onTogglePlan={() => toggleStop(s)}
                            onSelect={() => openStation(key)}
                            onHighlight={(on) => setHighlightedKey(on ? key : null)}
                            highlighted={highlightedKey === key}
                          />
                        );
                      })}
                    </ul>
                    {others.length > 0 ? (
                      <button
                        type="button"
                        onClick={() => setShowAll((all) => !all)}
                        className="self-start py-2 text-[15px] font-bold text-accent hover:text-accent-strong"
                      >
                        {showAll ? "Ver solo las recomendadas" : `Ver las ${total} gasolineras de la ruta`}
                      </button>
                    ) : null}
                  </>
                )}
              </>
            )}
          </div>

          <div className="shrink-0 px-3 pt-1 pb-[max(0.75rem,env(safe-area-inset-bottom))] lg:border-t lg:border-rule lg:px-4 lg:py-3">
            <TuRutaBar
              stops={stops.list.map((s) => ({ key: stationKey(s), kmOnRoute: s.km_on_route }))}
              planHref={serializeSearch("/ruta/hoja", params)}
              routeKm={search.data?.route_km ?? routeKm}
            />
          </div>
        </section>

        <div className="absolute inset-0 lg:static lg:min-w-0 lg:flex-1">
          {route.data ? (
            <RouteMapLazy
              track={route.data.track.coordinates}
              stations={mapPlates}
              otherStations={mapDots}
              stopKeys={stops.keys}
              focusedKey={focusedKey}
              highlightedKey={highlightedKey}
              onStationSelect={openStation}
              padding={
                isDesktop
                  ? { top: 0, bottom: 0, left: 0, right: 0 }
                  : { top: topHeight + 12, bottom: panelHeight, left: 0, right: 0 }
              }
            />
          ) : (
            <div className="size-full bg-map-land" />
          )}
        </div>

        {/* Móvil: tarjeta de la ruta con "Cambiar" y la frescura de los precios, sobre el mapa. */}
        <div ref={topRef} className="absolute inset-x-3 top-3 z-10 flex flex-col items-start gap-2 lg:hidden">
          <header className="flex w-full items-center gap-3 rounded-card border border-rule bg-surface py-2 pr-2 pl-3.5 shadow-float">
            <RouteGlyph />
            <div className="min-w-0 flex-1">
              <p className="m-0 truncate text-[17px] leading-tight font-bold">{routeTitle(source)}</p>
              <p className="m-0 mt-0.5 truncate font-mono text-xs text-muted">{routeSummary}</p>
            </div>
            <Button variant="secondary" onClick={() => setSearchOpen(true)}>
              Cambiar
            </Button>
          </header>
          {search.data ? (
            <FreshnessPill
              status={search.data.prices.status}
              ageMinutes={search.data.prices.age_minutes ?? null}
            />
          ) : null}
        </div>
      </div>

      <dialog
        ref={searchDialog}
        aria-labelledby="change-title"
        onClose={() => setSearchOpen(false)}
        className="m-0 mt-auto max-h-[92dvh] w-full max-w-none rounded-t-sheet border-0 bg-surface p-0 text-ink backdrop:bg-ink/40 lg:hidden"
      >
        <div className="flex flex-col gap-4 p-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
          <div className="flex items-center justify-between">
            <h2 id="change-title" className="m-0 text-xl font-bold">
              Cambiar la búsqueda
            </h2>
            <button
              type="button"
              aria-label="Cerrar"
              className="inline-flex size-11 items-center justify-center rounded-field hover:bg-rule-soft"
              onClick={() => setSearchOpen(false)}
            >
              <CloseIcon size={20} />
            </button>
          </div>
          {searchBar("column", () => setSearchOpen(false))}
        </div>
      </dialog>
    </div>
  );
}

function PriceValue({ children }: { children: ReactNode }) {
  return (
    <>
      {children}
      <span className="text-xs"> €/L</span>
    </>
  );
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
