/**
 * El GPX subido se guarda en el dispositivo (IndexedDB): un archivo no cabe en la URL, y así la
 * búsqueda sobrevive a recargar la página. Solo se guarda el último.
 */
import { del, get, set } from "idb-keyval";

const KEY = "gasolineras:gpx-upload";

/** Mismo límite que la API (POST /route/gpx). */
export const MAX_GPX_BYTES = 15 * 1024 * 1024;

export interface StoredGpx {
  name: string;
  bytes: ArrayBuffer;
  savedAt: string;
}

export async function saveGpx(file: File): Promise<void> {
  const stored: StoredGpx = {
    name: file.name,
    bytes: await file.arrayBuffer(),
    savedAt: new Date().toISOString(),
  };
  await set(KEY, stored);
}

export async function loadGpx(): Promise<StoredGpx | undefined> {
  return get<StoredGpx>(KEY);
}

export async function clearGpx(): Promise<void> {
  await del(KEY);
}

/** Comprobación previa a subir: mensaje para el usuario o null si vale. */
export function validateGpxFile(file: File): string | null {
  if (!/\.gpx$/i.test(file.name))
    return "Elige un archivo .gpx (el que exportas de Wikiloc, Calimoto, Kurviger…).";
  if (file.size === 0) return "El archivo está vacío.";
  if (file.size > MAX_GPX_BYTES) return "El archivo supera el máximo de 15 MB.";
  return null;
}
