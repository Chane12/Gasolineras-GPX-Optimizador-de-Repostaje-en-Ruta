"use client";

import { useCallback, useEffect, useState } from "react";

import { isOpenAt } from "@/lib/opening-hours";

/** "Abierta cuando pases" (punto 10b): hora de salida y velocidad media, recordadas en el dispositivo. */
export interface PassingSettings {
  enabled: boolean;
  /** Fecha y hora de salida, en hora local ("2026-10-19T07:30"). */
  departure: string;
  speedKmh: number;
  hideClosed: boolean;
}

export interface PassingStatus {
  eta: Date;
  /** null si el horario del MITECO no se entiende. */
  open: boolean | null;
}

const STORAGE_KEY = "gasolineras:al-pasar";
export const DEFAULT_SPEED_KMH = 80;

const pad = (n: number) => String(n).padStart(2, "0");
/** Fecha y hora local en el formato de <input type="datetime-local">. */
export function toLocalInput(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** Ahora, redondeado al siguiente cuarto de hora. */
function nextQuarter(now = new Date()): string {
  const d = new Date(now);
  d.setSeconds(0, 0);
  d.setMinutes(Math.ceil((d.getMinutes() + 1) / 15) * 15);
  return toLocalInput(d);
}

function load(): PassingSettings {
  const defaults: PassingSettings = {
    enabled: false,
    departure: nextQuarter(),
    speedKmh: DEFAULT_SPEED_KMH,
    hideClosed: false,
  };
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "null") as Partial<PassingSettings> | null;
    if (!saved) return defaults;
    const merged = { ...defaults, ...saved };
    // Una salida guardada que ya pasó hace horas no sirve: se propone la de ahora.
    if (new Date(merged.departure).getTime() < Date.now() - 6 * 3600_000)
      merged.departure = defaults.departure;
    return merged;
  } catch {
    return defaults;
  }
}

/** Hora estimada de paso por el km dado de la ruta. */
export function etaAt(settings: Pick<PassingSettings, "departure" | "speedKmh">, km: number): Date {
  const start = new Date(settings.departure).getTime();
  return new Date(start + (km / Math.max(5, settings.speedKmh)) * 3600_000);
}

export function usePassingTime() {
  // El servidor no tiene almacenamiento: allí son los valores por defecto (nada se pinta con ellos hasta que
  // llegan los resultados, ya en el navegador).
  const [settings, setSettings] = useState<PassingSettings>(load);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    } catch {
      // Sin almacenamiento: dura lo que la página.
    }
  }, [settings]);

  const update = useCallback((next: Partial<PassingSettings>) => setSettings((s) => ({ ...s, ...next })), []);

  const { enabled, departure, speedKmh } = settings;
  const statusOf = useCallback(
    (station: { km_on_route: number; schedule?: string | null; open_24h: boolean }): PassingStatus | null => {
      if (!enabled) return null;
      const eta = etaAt({ departure, speedKmh }, station.km_on_route);
      return { eta, open: station.open_24h ? true : isOpenAt(station.schedule, eta) };
    },
    [enabled, departure, speedKmh],
  );

  return { settings, update, statusOf };
}
