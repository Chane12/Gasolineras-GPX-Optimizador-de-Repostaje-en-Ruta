"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import * as maplibregl from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { IconButton } from "@/components/button";
import { Hito } from "@/components/hito";
import { FitIcon } from "@/components/icons";
import { PricePlate } from "@/components/price-plate";
import { formatKm, formatPrice } from "@/lib/format";
import { type Bounds, plateTones, type Station, stationKey, trackBounds } from "@/lib/map/geo";
import { buildMapStyle, readMapPalette, type TrackCoordinates } from "@/lib/map/style";

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
  stations: readonly Station[];
  /** Paradas elegidas (claves de `stationKey`): llevan su hito junto a la placa. */
  stopKeys?: ReadonlySet<string>;
  /** Gasolinera elegida en la lista: el mapa se centra en ella y la resalta. */
  focusedKey?: string | null;
  onStationSelect?: (key: string) => void;
  /** Lo que tapan la tarjeta de arriba y la hoja de abajo: el encuadre lo deja libre. */
  padding?: MapPadding;
}

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
  return slots;
}

/**
 * Mapa de la ruta con las placas de precio (diseno.md, «Mapa»). Complementa a la lista, que es la
 * vista accesible principal: todo lo que se hace aquí se puede hacer también desde ella.
 */
export function RouteMap({
  track,
  stations,
  stopKeys,
  focusedKey = null,
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
    const apply = () => map.setStyle(buildMapStyle(readMapPalette(), track), { diff: true });
    apply();
    const scheme = window.matchMedia("(prefers-color-scheme: dark)");
    scheme.addEventListener("change", apply);
    return () => scheme.removeEventListener("change", apply);
  }, [map, track]);

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
    const station = stations.find((s) => stationKey(s) === focusedKey);
    if (!station) return;
    map.easeTo({
      center: [station.lon, station.lat],
      zoom: Math.max(map.getZoom(), FOCUS_ZOOM),
      padding: paddingRef.current,
      animate: !reducedMotion(),
    });
  }, [map, focusedKey, stations]);

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
  const slots = useMarkers(map, markerItems);
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
        const focused = key === focusedKey;
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
              aria-label={`${s.name}, ${formatPrice(s.price)} euros por litro, km ${formatKm(s.km_on_route)}${isStop ? ", en tus paradas" : ""}`}
              className={`block cursor-pointer rounded-plate p-0 transition-transform ${focused ? "scale-115" : ""}`}
            >
              <PricePlate price={s.price} tone={tones[i] ?? "suggested"} />
            </button>
          </span>,
          element,
          key,
        );
      })}
      <div
        className="pointer-events-none absolute inset-x-3 flex items-end justify-between gap-3"
        style={{ bottom: padding.bottom + 8 }}
      >
        <p className="pointer-events-auto m-0 rounded-plate bg-surface/85 px-1.5 py-0.5 text-[11px] text-muted">
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
            className="pointer-events-auto"
            icon={<FitIcon />}
            onClick={() => fitRoute(map, bounds, padding, true)}
          />
        ) : null}
      </div>
    </div>
  );
}
