"use client";

import { useEffect, useRef, useState } from "react";

import { detourInBrowser } from "@/lib/browser-routing";
import { stationKey } from "@/lib/map/geo";

import { api, type ApiClient, type Schemas, unwrap } from "./client";

export interface DetourInfo {
  /** Ida desde la ruta y vuelta, por carretera; null si aún no se sabe o no se pudo calcular. */
  km: number | null;
  minutes: number | null;
  /** Peticiones hechas para esta gasolinera (para no reintentar sin fin). */
  attempts: number;
}

type StationLike = Pick<Schemas["Station"], "id" | "lat" | "lon">;

/** Lo que se espera al servidor antes de calcular los desvíos en el navegador. */
const DETOURS_SERVER_WAIT_MS = 8_000;

/** Desvíos que el navegador calcula por su cuenta en cada tanda, si el servidor no pudo. */
const BROWSER_DETOURS_MAX = 12;

/** Máximo de gasolineras por petición (límite de la API). */
export const DETOURS_BATCH = 30;
/** Espera antes de cada reintento de los que faltan (el OSRM público a veces limita): 0 = la primera vez. */
export const RETRY_DELAYS_MS = [0, 4_000, 12_000] as const;

/**
 * Desvíos reales (OSRM) de las gasolineras dadas, pedidos en segundo plano: la lista se ve en cuanto llega
 * la búsqueda y los desvíos se rellenan según llegan. Si el servicio de rutas no da abasto (`complete:
 * false`), se vuelve a pedir solo lo que falta, tras una pausa, hasta 3 veces. Se guardan por ruta.
 */
export function useDetours(
  route: { key: string; track: { coordinates: number[][] } } | null,
  stations: readonly StationLike[],
  client: ApiClient = api,
): ReadonlyMap<string, DetourInfo> {
  const [state, setState] = useState<{ routeKey: string | null; detours: Map<string, DetourInfo> }>({
    routeKey: null,
    detours: new Map(),
  });
  const inFlight = useRef(new Set<string>());
  const routeKey = route?.key ?? null;
  // Al cambiar de ruta, los desvíos anteriores ya no valen.
  const detours = state.routeKey === routeKey ? state.detours : EMPTY;

  useEffect(() => {
    if (!route) return;
    const pending = stations.filter((s) => {
      const key = stationKey(s);
      const info = detours.get(key);
      if (inFlight.current.has(key)) return false;
      return !info || (info.km === null && info.attempts < RETRY_DELAYS_MS.length);
    });
    if (pending.length === 0) return;
    const attempts = Math.min(...pending.map((s) => detours.get(stationKey(s))?.attempts ?? 0));
    const delay = RETRY_DELAYS_MS[attempts] ?? 0;
    const forRoute = route.key;

    const timer = setTimeout(() => {
      const batches: StationLike[][] = [];
      for (let i = 0; i < pending.length; i += DETOURS_BATCH)
        batches.push(pending.slice(i, i + DETOURS_BATCH));
      for (const batch of batches) {
        const keys = batch.map(stationKey);
        keys.forEach((k) => inFlight.current.add(k));
        // Si el servidor tarda (está insistiendo a un OSRM que no le responde), no se le espera: a los
        // DETOURS_SERVER_WAIT_MS se cuenta como fallo y el navegador los calcula por su cuenta.
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), DETOURS_SERVER_WAIT_MS);
        unwrap(
          client.POST("/detours", {
            signal: controller.signal,
            body: {
              track: route.track as Schemas["DetoursRequest"]["track"],
              stations: batch.map((s) => ({ id: s.id ?? null, lat: s.lat, lon: s.lon })),
            },
          }),
        )
          .then((response) =>
            response.detours.map((d) => ({ km: d.detour_km ?? null, minutes: d.detour_min ?? null })),
          )
          // Sin red, API caída, tiempo agotado o respuesta inesperada: cuenta como intento, sin desvío.
          .catch(() => batch.map(() => ({ km: null, minutes: null })))
          .finally(() => clearTimeout(timer))
          // Los que el servidor no consiguió (OSRM le limita a veces), los pide el navegador directamente,
          // de uno en uno y como mucho los primeros BROWSER_DETOURS_MAX de cada tanda.
          .then(async (results) => {
            let asked = 0;
            for (const [i, result] of results.entries()) {
              const station = batch[i];
              if (result.km !== null || !station || asked >= BROWSER_DETOURS_MAX) continue;
              asked++;
              try {
                results[i] = await detourInBrowser(route.track.coordinates, station);
              } catch {
                // Tampoco desde el navegador: se queda sin desvío y se reintenta más tarde.
              }
            }
            return results;
          })
          .then((results) => {
            keys.forEach((k) => inFlight.current.delete(k));
            setState((current) => {
              const base = current.routeKey === forRoute ? current.detours : new Map<string, DetourInfo>();
              const next = new Map(base);
              keys.forEach((key, i) => {
                const result = results[i] ?? { km: null, minutes: null };
                next.set(key, { ...result, attempts: (base.get(key)?.attempts ?? 0) + 1 });
              });
              return { routeKey: forRoute, detours: next };
            });
          });
      }
    }, delay);
    return () => clearTimeout(timer);
  }, [route, stations, detours, client]);

  return detours;
}

const EMPTY: Map<string, DetourInfo> = new Map();
