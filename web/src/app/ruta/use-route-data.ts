"use client";

import { useQueryStates } from "nuqs";
import { useCallback, useEffect, useMemo, useState } from "react";

import { api, type ApiClient } from "@/lib/api/client";
import { routeSourceKey, useRoute, useStationSearch } from "@/lib/api/queries";
import { type Station, stationKey } from "@/lib/map/geo";
import { routeSourceFrom, searchOptionsFrom, searchParams } from "@/lib/search-params";
import { autoSegmentKm, RECOMMENDED_CHEAPEST, trackLengthKm } from "@/lib/stations";
import { loadSavedStops, type SavedStop, saveStop } from "@/lib/stop-store";

const NO_STATIONS: Station[] = [];

/**
 * Paradas: la lista de claves vive en la URL (se comparte y sobrevive a recargar); los datos de cada una
 * salen de los resultados actuales o, si un filtro la dejó fuera, de la copia guardada en el dispositivo.
 */
export function useStops(
  keys: readonly string[],
  setKeys: (keys: string[]) => void,
  available: readonly Station[],
) {
  const [saved, setSaved] = useState<Record<string, SavedStop>>({});
  useEffect(() => {
    let alive = true;
    void loadSavedStops().then((stops) => {
      if (alive) setSaved(stops);
    });
    return () => {
      alive = false;
    };
  }, []);

  const list = useMemo(() => {
    const byKey = new Map(available.map((s) => [stationKey(s), s]));
    return keys
      .map((key) => byKey.get(key) ?? saved[key]?.station)
      .filter((s): s is Station => s !== undefined)
      .sort((a, b) => a.km_on_route - b.km_on_route);
  }, [keys, available, saved]);
  const keySet = useMemo(() => new Set(keys), [keys]);

  const toggle = useCallback(
    (station: Station) => {
      const key = stationKey(station);
      if (keySet.has(key)) {
        setKeys(keys.filter((k) => k !== key));
        return;
      }
      setKeys([...keys, key]);
      setSaved((current) => ({ ...current, [key]: { station, savedAt: new Date().toISOString() } }));
      void saveStop(key, station);
    },
    [keys, keySet, setKeys],
  );

  /** Sustituye todas las paradas (p. ej. por las del planificador). */
  const replaceAll = useCallback(
    (stations: readonly Station[]) => {
      setKeys(stations.map(stationKey));
      const now = new Date().toISOString();
      setSaved((current) => ({
        ...current,
        ...Object.fromEntries(stations.map((s) => [stationKey(s), { station: s, savedAt: now }])),
      }));
      stations.forEach((s) => void saveStop(stationKey(s), s));
    },
    [setKeys],
  );

  return { list, keys: keySet, toggle, replaceAll };
}

/** Todo lo que necesitan la pantalla de la ruta y la hoja de ruta: ruta, búsqueda y paradas, desde la URL. */
export function useRouteData(client: ApiClient = api) {
  const [params, setParams] = useQueryStates(searchParams);
  const source = routeSourceFrom(params);

  const route = useRoute(source, client);
  const routeKm = useMemo(() => (route.data ? trackLengthKm(route.data.track.coordinates) : 0), [route.data]);
  const routeKey = source ? routeSourceKey(source) : null;
  const routeForSearch = useMemo(
    () => (route.data && routeKey ? { key: routeKey, track: route.data.track } : null),
    [route.data, routeKey],
  );
  const options = {
    ...searchOptionsFrom(params),
    top_n: RECOMMENDED_CHEAPEST,
    segment_km: autoSegmentKm(routeKm),
    include_others: true,
  };
  const search = useStationSearch(routeForSearch, options, client);

  const recommended = search.data?.stations ?? NO_STATIONS;
  const others = search.data?.other_stations ?? NO_STATIONS;
  const all = useMemo(() => [...recommended, ...others], [recommended, others]);
  const setStopKeys = useCallback(
    (keys: string[]) => void setParams({ paradas: keys.length > 0 ? keys : null }),
    [setParams],
  );
  const stops = useStops(params.paradas, setStopKeys, all);

  return { params, setParams, source, route, routeKm, routeForSearch, search, recommended, others, stops };
}
