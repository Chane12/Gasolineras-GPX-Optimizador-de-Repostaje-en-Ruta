/**
 * ¿Abierta a una hora dada? A partir del horario tal como lo publica el MITECO:
 * "L-D: 24H", "L-D: 06:00-22:00", "L-V: 06:00-22:00; S-D: 07:00-22:00", "L-S: 06:00-02:00" (pasa de
 * medianoche)… Si el formato no se entiende, la respuesta es `null`: mejor no decir nada que equivocarse.
 * No tiene en cuenta los festivos (el MITECO no los publica).
 */

const DAYS = ["L", "M", "X", "J", "V", "S", "D"] as const; // lunes … domingo

interface Segment {
  days: Set<number>; // 0 = lunes … 6 = domingo
  /** Minutos desde la medianoche; `end` puede ser menor que `start` (cierra pasada la medianoche). */
  start: number;
  end: number;
  allDay: boolean;
}

const SEGMENT =
  /^\s*([LMXJVSD])(?:\s*-\s*([LMXJVSD]))?\s*:\s*(24H|(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2}))\s*$/i;

function parse(schedule: string): Segment[] | null {
  const parts = schedule.split(";").filter((p) => p.trim());
  if (parts.length === 0) return null;
  const segments: Segment[] = [];
  for (const part of parts) {
    const m = part.match(SEGMENT);
    if (!m) return null;
    const [, fromDay = "", toDay, hours = "", h1 = "0", m1 = "0", h2 = "0", m2 = "0"] = m;
    const from = DAYS.indexOf(fromDay.toUpperCase() as (typeof DAYS)[number]);
    const to = toDay ? DAYS.indexOf(toDay.toUpperCase() as (typeof DAYS)[number]) : from;
    if (from < 0 || to < from) return null;
    const days = new Set<number>();
    for (let d = from; d <= to; d++) days.add(d);
    const allDay =
      hours.toUpperCase() === "24H" || (h1 === "00" && m1 === "00" && h2 === "23" && m2 === "59");
    segments.push({ days, start: Number(h1) * 60 + Number(m1), end: Number(h2) * 60 + Number(m2), allDay });
  }
  // "L: 24H" o "L: 07:00-23:00" a secas (solo el lunes) aparece en muchas gasolineras y casi seguro quiere
  // decir "todos los días": es ambiguo, así que no se afirma nada.
  const only = segments[0];
  if (segments.length === 1 && only && only.days.size === 1) return null;
  return segments;
}

/** Día de la semana con el lunes = 0. */
const weekday = (date: Date) => (date.getDay() + 6) % 7;

export function isOpenAt(schedule: string | null | undefined, date: Date): boolean | null {
  if (!schedule) return null;
  const segments = parse(schedule);
  if (!segments) return null;
  const today = weekday(date);
  const yesterday = (today + 6) % 7;
  const minutes = date.getHours() * 60 + date.getMinutes();
  return segments.some((s) => {
    if (s.allDay) return s.days.has(today);
    if (s.end > s.start) return s.days.has(today) && minutes >= s.start && minutes < s.end;
    // Pasa de medianoche (06:00-02:00 o 22:00-06:00): abierta desde la apertura de hoy, o hasta el cierre
    // si el tramo empezó ayer.
    return (s.days.has(today) && minutes >= s.start) || (s.days.has(yesterday) && minutes < s.end);
  });
}
