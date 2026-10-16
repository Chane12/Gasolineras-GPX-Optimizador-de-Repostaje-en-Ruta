"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import * as maplibregl from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { IconButton } from "@/components/button";
import { Hito } from "@/components/hito";
import { FitIcon, MinusIcon, PlusIcon } from "@/components/icons";
import { PricePlate } from "@/components/price-plate";
import { formatKm, formatPrice } from "@/lib/format";
import {
  type Bounds,
  overlappingPlates,
  plateTones,
  type Station,
  stationKey,
  trackBounds,
} from "@/lib/map/geo";
import { buildMapStyle, OTHERS_LAYER, readMapPalette, type TrackCoordinates } from "@/lib/map/style";

// MapLibre 6 busca su worker junto a su propio módulo; con el empaquetado de Next ese archivo no está
// ahí, así que se le pasa la URL del worker empaquetado como recurso.
maplibregl.setWorkerUrl(new URL("maplibre-gl/dist/maplibre-gl-worker.mjs", import.meta.url).href);

export interface MapPadding {
  top: number;
  bottom: number;
  left: number;
  right: number;
}

export interface RouteMapProps {
  track: TrackCoordinates;
  /** Con placa de precio: las recomendadas (y las paradas o la elegida, aunque no lo sean). */
  stations: readonly Station[];
  /** El resto del corredor: puntos pequeños, sin precio (se pueden tocar). */
  otherStations?: readonly Station[];
  /** Paradas elegidas (claves de `stationKey`): llevan su hito junto a la placa. */
  stopKeys?: ReadonlySet<string>;
  /** Gasolinera elegida en la lista: el mapa se centra en ella y la resalta. */
  focusedKey?: string | null;
  /** Fila con el ratón o el foco encima: su placa se resalta, sin mover el mapa. */
  highlightedKey?: string | null;
  onStationSelect?: (key: string) => void;
  /** Lo que tapan la tarjeta de arriba y la hoja de abajo: el encuadre lo deja libre. */
  padding?: MapPadding;
}

const NO_STATIONS: readonly Station[] = [];
const DEFAULT_PADDING: MapPadding = { top: 24, bottom: 24, left: 24, right: 24 };
const FIT_MARGIN = 36;
const FOCUS_ZOOM = 13;

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function fitRoute(map: maplibregl.Map, bounds: Bounds, padding: MapPadding, animate: boolean) {
  map.fitBounds(bounds, {
    padding: {
      top: padding.top + FIT_MARGIN,
      bottom: padding.bottom + FIT_MARGIN,
      left: padding.left + FIT_MARGIN,
      right: padding.right + FIT_MARGIN,
    },
    animate: animate && !reducedMotion(),
  });
}

/** Un marcador de MapLibre cuyo contenido pinta React (a través de un portal). */
interface MarkerSlot {
  key: string;
  element: HTMLElement;
}

function useMarkers(
  map: maplibregl.Map | null,
  items: readonly { key: string; lngLat: [number, number]; zIndex: number }[],
  raised: ReadonlySet<string> = new Set(),
): MarkerSlot[] {
  // Nodos sueltos (aún fuera del documento) donde React pinta cada marcador con un portal.
  const slots = useMemo(
    () =>
      map
        ? items.map((item) => {
            const element = document.createElement("div");
            element.style.zIndex = String(item.zIndex);
            return { key: item.key, element };
          })
        : [],
    [map, items],
  );
  useEffect(() => {
    if (!map) return;
    const markers = slots.map((slot, i) =>
      new maplibregl.Marker({ element: slot.element, anchor: "bottom" })
        .setLngLat(items[i]?.lngLat ?? [0, 0])
        .addTo(map),
    );
    return () => markers.forEach((marker) => marker.remove());
  }, [map, items, slots]);
  // Los marcadores resaltados, por encima de los demás.
  useEffect(() => {
    slots.forEach((slot, i) => {
      slot.element.style.zIndex = String(raised.has(slot.key) ? 10 : (items[i]?.zIndex ?? 1));
    });
  }, [slots, items, raised]);
  return slots;
}

/**
 * Mapa de la ruta con las placas de precio (diseno.md, «Mapa»). Complementa a la lista, que es la
 * vista accesible principal: todo lo que se hace aquí se puede hacer también desde ella.
 */
export function RouteMap({
  track,
  stations,
  otherStations = NO_STATIONS,
  stopKeys,
  focusedKey = null,
  highlightedKey = null,
  onStationSelect,
  padding = DEFAULT_PADDING,
}: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [map, setMap] = useState<maplibregl.Map | null>(null);
  const bounds = useMemo(() => trackBounds(track), [track]);
  const paddingRef = useRef(padding);
  useEffect(() => {
    paddingRef.current = padding;
  });

  // Crear el mapa una vez; la ruta y el tema cambian el estilo, no el mapa.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const instance = new maplibregl.Map({
      container,
      style: buildMapStyle(readMapPalette(), []),
      center: [-3.7, 40.2],
      zoom: 5,
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
      touchPitch: false,
      cooperativeGestures: false,
    });
    instance.touchZoomRotate.disableRotation();
    instance.keyboard.disableRotation();
    setMap(instance);
    return () => {
      instance.remove();
      setMap(null);
    };
  }, []);

  // Estilo con la ruta; se rehace si cambia el modo claro/oscuro del sistema.
  useEffect(() => {
    if (!map) return;
    const dots = otherStations.map((st) => ({ key: stationKey(st), lon: st.lon, lat: st.lat }));
    const apply = () => map.setStyle(buildMapStyle(readMapPalette(), track, dots), { diff: true });
    apply();
    const scheme = window.matchMedia("(prefers-color-scheme: dark)");
    scheme.addEventListener("change", apply);
    return () => scheme.removeEventListener("change", apply);
  }, [map, track, otherStations]);

  // Tocar un punto lo elige, como una placa.
  const onSelectRef = useRef(onStationSelect);
  useEffect(() => {
    onSelectRef.current = onStationSelect;
  });
  useEffect(() => {
    if (!map) return;
    const click = (e: maplibregl.MapLayerMouseEvent) => {
      const key = e.features?.[0]?.properties?.key;
      if (typeof key === "string") onSelectRef.current?.(key);
    };
    const enter = () => (map.getCanvas().style.cursor = "pointer");
    const leave = () => (map.getCanvas().style.cursor = "");
    map.on("click", OTHERS_LAYER, click);
    map.on("mouseenter", OTHERS_LAYER, enter);
    map.on("mouseleave", OTHERS_LAYER, leave);
    return () => {
      map.off("click", OTHERS_LAYER, click);
      map.off("mouseenter", OTHERS_LAYER, enter);
      map.off("mouseleave", OTHERS_LAYER, leave);
    };
  }, [map]);

  // Encuadrar la ruta al cargarla, y otra vez si cambia lo que tapa el mapa (la hoja crece al llegar
  // los resultados), mientras el usuario no lo haya movido él mismo.
  const userMovedRef = useRef(false);
  useEffect(() => {
    if (!map) return;
    const onUserMove = (event: { originalEvent?: unknown }) => {
      if (event.originalEvent) userMovedRef.current = true;
    };
    map.on("movestart", onUserMove);
    return () => {
      map.off("movestart", onUserMove);
    };
  }, [map]);
  useEffect(() => {
    userMovedRef.current = false;
  }, [bounds]);
  useEffect(() => {
    if (map && bounds && !userMovedRef.current) fitRoute(map, bounds, paddingRef.current, false);
  }, [map, bounds, padding.top, padding.bottom]);

  // Centrar en la gasolinera elegida en la lista.
  useEffect(() => {
    if (!map || !focusedKey) return;
    const station = [...stations, ...otherStations].find((s) => stationKey(s) === focusedKey);
    if (!station) return;
    map.easeTo({
      center: [station.lon, station.lat],
      zoom: Math.max(map.getZoom(), FOCUS_ZOOM),
      padding: paddingRef.current,
      animate: !reducedMotion(),
    });
  }, [map, focusedKey, stations, otherStations]);

  const tones = useMemo(() => plateTones(stations), [stations]);
  const markerItems = useMemo(
    () =>
      stations.map((s, i) => ({
        key: stationKey(s),
        lngLat: [s.lon, s.lat] as [number, number],
        // Las más baratas por encima de las demás.
        zIndex: tones[i] === "best" ? 3 : tones[i] === "suggested" ? 2 : 1,
      })),
    [stations, tones],
  );
  const raised = useMemo(
    () => new Set([focusedKey, highlightedKey].filter((k): k is string => k !== null)),
    [focusedKey, highlightedKey],
  );
  const slots = useMarkers(map, markerItems, raised);

  // Placas que se taparían: queda la más importante y las demás pasan a punto (se recalcula al mover).
  const [hiddenPlates, setHiddenPlates] = useState<ReadonlySet<string>>(new Set());
  useEffect(() => {
    if (!map) return;
    const priorityOf = (st: Station, i: number) => {
      const key = stationKey(st);
      if (raised.has(key) || stopKeys?.has(key)) return 0;
      return tones[i] === "best" ? 1 : 2 + st.price;
    };
    const update = () => {
      const plates = stations.map((st, i) => {
        const point = map.project([st.lon, st.lat]);
        return { key: stationKey(st), x: point.x, y: point.y, priority: priorityOf(st, i) };
      });
      const next = overlappingPlates(plates);
      setHiddenPlates((current) =>
        current.size === next.size && [...next].every((k) => current.has(k)) ? current : next,
      );
    };
    update();
    map.on("moveend", update);
    map.on("resize", update);
    return () => {
      map.off("moveend", update);
      map.off("resize", update);
    };
  }, [map, stations, tones, raised, stopKeys]);
  const endpoints = useMemo(() => {
    const first = track[0];
    const last = track[track.length - 1];
    if (!first || !last || track.length < 2) return [];
    return [
      { key: "origin", lngLat: [first[0] ?? 0, first[1] ?? 0] as [number, number], zIndex: 0 },
      { key: "destination", lngLat: [last[0] ?? 0, last[1] ?? 0] as [number, number], zIndex: 0 },
    ];
  }, [track]);
  const endpointSlots = useMarkers(map, endpoints);

  const byKey = useMemo(() => new Map(stations.map((s, i) => [stationKey(s), { s, i }])), [stations]);

  return (
    <div className="relative size-full bg-map-land">
      <div
        ref={containerRef}
        className="route-map size-full"
        role="region"
        aria-label="Mapa de la ruta con los precios de las gasolineras"
      />
      {endpointSlots.map(({ key, element }) =>
        createPortal(
          key === "origin" ? (
            <span
              aria-hidden="true"
              className="block size-3.5 translate-y-1/2 rounded-full border-[3px] border-accent bg-bg"
            />
          ) : (
            <span
              aria-hidden="true"
              className="block size-3.5 translate-y-1/2 border-[2.5px] border-bg bg-accent"
            />
          ),
          element,
          key,
        ),
      )}
      {slots.map(({ key, element }) => {
        const entry = byKey.get(key);
        if (!entry) return null;
        const { s, i } = entry;
        const isStop = stopKeys?.has(key) ?? false;
        const focused = key === focusedKey || key === highlightedKey;
        const label = `${s.name}, ${formatPrice(s.price)} euros por litro, km ${formatKm(s.km_on_route)}${isStop ? ", en tus paradas" : ""}`;
        if (hiddenPlates.has(key)) {
          return createPortal(
            <button
              type="button"
              onClick={() => onStationSelect?.(key)}
              aria-label={label}
              className="block translate-y-1/2 cursor-pointer p-1.5"
            >
              <span className="block size-2.5 rounded-full border-2 border-bg bg-ink" />
            </button>,
            element,
            key,
          );
        }
        return createPortal(
          <span className="relative flex items-end">
            {isStop ? (
              <span className="absolute right-full bottom-1.5 mr-1">
                <Hito km={s.km_on_route} size="sm" />
              </span>
            ) : null}
            <button
              type="button"
              onClick={() => onStationSelect?.(key)}
              aria-label={label}
              className={`block cursor-pointer rounded-plate p-0 transition-transform ${
                focused ? "scale-120 rounded-plate outline-2 outline-offset-2 outline-ink" : ""
              }`}
            >
              <PricePlate price={s.price} tone={tones[i] ?? "suggested"} />
            </button>
          </span>,
          element,
          key,
        );
      })}
      {map ? (
        <div
          role="group"
          aria-label="Controles del mapa"
          className="absolute top-4 right-4 hidden flex-col overflow-hidden rounded-card border border-rule bg-surface shadow-float lg:flex"
        >
          <IconButton
            label="Acercar"
            tone="plain"
            className="rounded-none text-ink"
            icon={<PlusIcon size={18} />}
            onClick={() => map.zoomIn()}
          />
          <IconButton
            label="Alejar"
            tone="plain"
            className="rounded-none border-t border-rule-soft text-ink"
            icon={<MinusIcon size={18} />}
            onClick={() => map.zoomOut()}
          />
          {bounds ? (
            <IconButton
              label="Ver toda la ruta"
              tone="plain"
              className="rounded-none border-t border-rule-soft text-ink"
              icon={<FitIcon size={18} />}
              onClick={() => fitRoute(map, bounds, padding, true)}
            />
          ) : null}
        </div>
      ) : null}
      <div
        className="pointer-events-none absolute inset-x-3 flex items-end justify-between gap-3 lg:inset-x-4"
        style={{ bottom: padding.bottom + 8 }}
      >
        <Legend />
        <p className="pointer-events-auto m-0 rounded-plate bg-surface/85 px-1.5 py-0.5 text-[11px] text-muted lg:order-last">
          <a href="https://openfreemap.org" target="_blank" rel="noopener" className="text-muted">
            OpenFreeMap
          </a>{" "}
          ·{" "}
          <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener" className="text-muted">
            © OpenMapTiles
          </a>{" "}
          ·{" "}
          <a
            href="https://www.openstreetmap.org/copyright"
            target="_blank"
            rel="noopener"
            className="text-muted"
          >
            © OpenStreetMap
          </a>
        </p>
        {bounds && map ? (
          <IconButton
            label="Ver toda la ruta"
            tone="floating"
            className="pointer-events-auto lg:hidden"
            icon={<FitIcon />}
            onClick={() => fitRoute(map, bounds, padding, true)}
          />
        ) : null}
      </div>
    </div>
  );
}

/** Leyenda del ordenador (maqueta Escritorio-Ruta): qué es cada marca del mapa. */
function Legend() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-auto hidden flex-wrap items-center gap-3.5 rounded-card border border-rule bg-surface px-3 py-2 text-[13px] font-semibold lg:flex"
    >
      <span className="inline-flex items-center gap-1.5">
        <span className="rounded-[3px] bg-accent px-1 font-mono text-[11px] text-on-accent">1,6</span>La más
        barata
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="rounded-[3px] border-[1.5px] border-ink px-1 font-mono text-[11px]">1,6</span>
        Recomendada
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="size-2 rounded-full bg-muted" />
        Otras
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="h-3 w-2.5 overflow-hidden rounded-t-[5px] rounded-b-[1px] border-[1.5px] border-hito-ink bg-hito-body">
          <span className="block h-1 bg-hito-red" />
        </span>
        Tu parada
      </span>
    </div>
  );
}
