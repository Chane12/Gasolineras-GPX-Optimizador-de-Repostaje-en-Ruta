/**
 * Copia en el dispositivo (IndexedDB) de cada parada elegida, con el precio del momento en que se eligió:
 * si luego un filtro la deja fuera de los resultados, la hoja de ruta la sigue mostrando.
 */
import { get, set } from "idb-keyval";

import type { Station } from "@/lib/map/geo";

const KEY = "gasolineras:paradas";
/** Solo las últimas: es una copia de seguridad, no un historial. */
const MAX_SAVED = 200;

export interface SavedStop {
  station: Station;
  savedAt: string;
}

export async function loadSavedStops(): Promise<Record<string, SavedStop>> {
  try {
    return (await get<Record<string, SavedStop>>(KEY)) ?? {};
  } catch {
    return {}; // navegación privada o IndexedDB bloqueado: sin copia, la web sigue funcionando
  }
}

export async function saveStop(key: string, station: Station): Promise<void> {
  try {
    const saved = await loadSavedStops();
    saved[key] = { station, savedAt: new Date().toISOString() };
    const entries = Object.entries(saved).sort((a, b) => b[1].savedAt.localeCompare(a[1].savedAt));
    await set(KEY, Object.fromEntries(entries.slice(0, MAX_SAVED)));
  } catch {
    // Sin IndexedDB: la parada sigue en la URL.
  }
}
