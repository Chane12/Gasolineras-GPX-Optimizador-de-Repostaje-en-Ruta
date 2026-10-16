"use client";

import Link from "next/link";
import { useState } from "react";

import { Button, ButtonLink, buttonClasses } from "@/components/button";
import { Hito } from "@/components/hito";
import {
  ChevronDownIcon,
  ChevronLeftIcon,
  CloseIcon,
  DownloadIcon,
  NavigateIcon,
  ShareIcon,
  WarningIcon,
} from "@/components/icons";
import { Logo } from "@/components/site-header";
import { api, type ApiClient } from "@/lib/api/client";
import { type DetourInfo, useDetours } from "@/lib/api/detours";
import { applyDiscounts, type PricedStation } from "@/lib/discounts";
import { useDiscounts } from "@/lib/use-discounts";
import { downloadGpx, MAX_GPX_STOPS, useGmapsUrl } from "@/lib/api/exports";
import type { RouteSource } from "@/lib/api/queries";
import { formatKm, formatPrice, formatShortKm } from "@/lib/format";
import { type Station, stationKey } from "@/lib/map/geo";
import { buildRoadbook, legLevel, type RoadbookRow } from "@/lib/roadbook";
import { LIMITS, normalizeOptions, serializeSearch } from "@/lib/search-params";
import { formatSchedule, formatStationName } from "@/lib/stations";

import { useRouteData } from "../use-route-data";

function routeName(source: RouteSource): string {
  if (source.kind === "text") return `${source.origin} → ${source.destination}`;
  return source.kind === "gpx" ? "Tu ruta GPX" : "Sierra de Gredos · ejemplo";
}

function placesOf(source: RouteSource): { start: string; end: string } {
  if (source.kind === "text") return { start: source.origin, end: source.destination };
  return { start: "Inicio del track", end: "Final del track" };
}

const timeFormat = new Intl.DateTimeFormat("es-ES", { hour: "2-digit", minute: "2-digit" });

/** Viñetas de tulipán de rally (diseno.md, "Roadbook"): salida, repostaje y llegada. */
function Tulip({ kind }: { kind: RoadbookRow["kind"] }) {
  return (
    <svg width="30" height="36" viewBox="0 0 34 40" aria-hidden="true" className="mx-auto text-ink">
      {kind === "start" ? (
        <>
          <circle cx="17" cy="32" r="5" fill="none" stroke="currentColor" strokeWidth="2.5" />
          <path
            d="M17 27V8M11 13l6-6 6 6"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </>
      ) : kind === "stop" ? (
        <>
          <circle cx="17" cy="34" r="4" fill="currentColor" />
          <path
            d="M17 30V6M17 18h9"
            fill="none"
            stroke="currentColor"
            strokeWidth="3"
            strokeLinecap="round"
          />
          <rect x="24" y="13" width="8" height="10" rx="1.5" className="fill-hito-red" />
        </>
      ) : (
        <>
          <path d="M17 34V12" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
          <rect x="10" y="4" width="14" height="10" fill="currentColor" />
        </>
      )}
    </svg>
  );
}

function detourText(detour: DetourInfo | undefined): string | null {
  return detour?.km != null ? `desvío ${formatShortKm(detour.km)} km` : null;
}

/** El trayecto con los hitos de las paradas, encima del roadbook. */
function RouteBand({ stops, routeKm }: { stops: readonly Station[]; routeKm: number }) {
  return (
    <div
      className="relative h-10"
      role="img"
      aria-label={`Trayecto de ${formatKm(routeKm)} km con ${stops.length} ${stops.length === 1 ? "parada" : "paradas"}`}
    >
      <div className="absolute inset-x-2 top-[18px] h-[3px] bg-ink" />
      <span className="absolute top-[11px] left-0 size-[17px] rounded-full border-[3.5px] border-accent bg-bg" />
      {stops.map((s) => (
        <span
          key={stationKey(s)}
          className="absolute top-0"
          style={{ left: `calc(${Math.min(100, (s.km_on_route / (routeKm || 1)) * 100)}% - 15px)` }}
        >
          <Hito km={s.km_on_route} size="sm" />
        </span>
      ))}
      <span className="absolute top-[11px] right-0 size-[17px] bg-accent" />
    </div>
  );
}

const PROFILES = [
  { label: "Moto", km: 250 },
  { label: "Coche", km: 600 },
  { label: "Gran autonomía", km: 900 },
] as const;

function AutonomyCheck({ autonomyKm, onChange }: { autonomyKm: number; onChange: (km: number) => void }) {
  const [open, setOpen] = useState(autonomyKm > 0);
  const [custom, setCustom] = useState("");
  const customKm = Number.parseInt(custom, 10);
  const customValid = customKm >= LIMITS.autonomiaKm.min && customKm <= LIMITS.autonomiaKm.max;
  return (
    <section className="rounded-card border border-rule print:hidden">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex min-h-[52px] w-full items-center justify-between gap-3 px-4 py-2.5 text-left"
      >
        <span>
          <span className="block text-[15px] font-bold">
            {autonomyKm > 0 ? `Autonomía: ${autonomyKm} km` : "Comprobar autonomía"}
          </span>
          <span className="block text-[13px] text-muted">Opcional · te avisamos de los tramos largos</span>
        </span>
        <ChevronDownIcon size={18} className={`shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open ? (
        <div className="flex flex-wrap items-center gap-2 border-t border-rule px-4 py-3">
          {PROFILES.map((p) => (
            <button
              key={p.km}
              type="button"
              aria-pressed={autonomyKm === p.km}
              onClick={() => onChange(p.km)}
              className={`h-10 rounded-field border-[1.5px] px-3 text-sm font-semibold ${
                autonomyKm === p.km ? "border-accent text-accent" : "border-field-border hover:bg-rule-soft"
              }`}
            >
              {p.label} · <span className="font-mono">{p.km}</span> km
            </button>
          ))}
          <form
            className="flex items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (customValid) onChange(customKm);
            }}
          >
            <label className="sr-only" htmlFor="plan-autonomy">
              Otra autonomía, en km
            </label>
            <input
              id="plan-autonomy"
              inputMode="numeric"
              placeholder="Otra (km)"
              value={custom}
              onChange={(e) => setCustom(e.target.value.replace(/\D/g, ""))}
              className="h-10 w-28 rounded-field border-[1.5px] border-field-border bg-surface px-3 font-mono text-sm"
            />
            <button
              type="submit"
              disabled={!customValid}
              className="h-10 rounded-field border-[1.5px] border-field-border px-3 text-sm font-semibold disabled:opacity-50"
            >
              Usar
            </button>
          </form>
          {autonomyKm > 0 ? (
            <button
              type="button"
              onClick={() => onChange(0)}
              className="py-2 text-[15px] font-bold text-accent"
            >
              Quitar
            </button>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

/**
 * Hoja de ruta (maquetas Escritorio-HojaDeRuta y Movil-HojaDeRuta): el roadbook con las paradas y cómo
 * llevársela (Google Maps, GPX, imprimir o PDF, enlace). Lee la búsqueda y las paradas de la URL.
 */
export function RoadbookView({ client = api }: { client?: ApiClient }) {
  const {
    params,
    setParams,
    source,
    route,
    routeKm,
    routeForSearch,
    search,
    stops: rawStops,
  } = useRouteData(client);
  // Con "Mis descuentos" (10c), los precios de la hoja son los que pagará el usuario.
  const { discounts } = useDiscounts();
  const stops = {
    ...rawStops,
    list: rawStops.list.map((s): PricedStation => applyDiscounts(s, discounts)),
  };
  const detours = useDetours(routeForSearch, stops.list, client);
  // Se prepara cuando ya se conocen las paradas (si no, se pediría una vez sin ellas).
  const gmaps = useGmapsUrl(
    search.data ? (routeForSearch?.key ?? null) : null,
    route.data?.track ?? null,
    stops.list,
    client,
  );
  const [gpxState, setGpxState] = useState<"idle" | "busy" | "error">("idle");
  const [shared, setShared] = useState(false);

  const backHref = serializeSearch("/ruta", params);
  const autonomyKm = normalizeOptions(params).autonomia;

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

  const totalKm = search.data?.route_km ?? routeKm;
  const rows = buildRoadbook(stops.list, totalKm, placesOf(source));
  const fetchedAt = search.data?.prices.fetched_at ? new Date(search.data.prices.fetched_at) : null;
  const loading =
    route.isPending || (search.isPending && stops.list.length === 0 && params.paradas.length > 0);
  const name = routeName(source);

  async function share() {
    const url = window.location.href;
    try {
      if (navigator.share) await navigator.share({ title: `Hoja de ruta · ${name}`, url });
      else await navigator.clipboard.writeText(url);
      setShared(true);
    } catch {
      // El usuario cerró el diálogo de compartir: nada que hacer.
    }
  }

  async function gpx() {
    if (!route.data) return;
    setGpxState("busy");
    try {
      await downloadGpx(route.data.track, stops.list, `Hoja de ruta ${name}`, client);
      setGpxState("idle");
    } catch {
      setGpxState("error");
    }
  }

  return (
    <div className="flex min-h-dvh flex-col pb-40 lg:pb-0 print:pb-0">
      <header className="flex items-center gap-4 border-b border-rule px-3 py-2 lg:px-6 print:hidden">
        <Link
          href="/"
          className="hidden text-ink no-underline lg:inline"
          aria-label="Gasolineras en Ruta, inicio"
        >
          <Logo />
        </Link>
        <Link
          href={backHref}
          className="inline-flex h-11 items-center gap-1 px-1 text-[15px] font-bold lg:ml-4"
        >
          <ChevronLeftIcon size={18} /> Volver a elegir paradas
        </Link>
      </header>

      <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-8 px-4 py-6 lg:flex-row lg:items-start lg:gap-12 lg:px-10 lg:py-8">
        <div className="flex min-w-0 flex-1 flex-col gap-5">
          <div>
            <p className="m-0 font-mono text-[11px] font-semibold tracking-[0.1em] text-muted uppercase">
              Hoja de ruta · {search.data?.fuel.label ?? "…"}
            </p>
            <h1 className="m-0 mt-1 text-[28px] leading-tight font-bold tracking-[-0.02em] lg:text-[34px]">
              {name}
            </h1>
            <p className="m-0 mt-1.5 text-[15px] text-muted">
              <span className="font-mono">{formatKm(totalKm)}</span> km ·{" "}
              <span className="font-mono">{stops.list.length}</span>{" "}
              {stops.list.length === 1 ? "parada" : "paradas"}
              {fetchedAt ? (
                <>
                  {" "}
                  · precios de las <span className="font-mono">{timeFormat.format(fetchedAt)}</span>
                </>
              ) : null}
            </p>
          </div>

          {loading ? (
            <p role="status" className="m-0 text-muted">
              Preparando tu hoja de ruta…
            </p>
          ) : stops.list.length === 0 ? (
            <div className="flex flex-col items-start gap-3">
              <p className="m-0">Aún no has elegido paradas para esta ruta.</p>
              <Link href={backHref} className={buttonClasses()}>
                Elegir paradas
              </Link>
            </div>
          ) : (
            <>
              <RouteBand stops={stops.list} routeKm={totalKm} />
              <table className="w-full border-collapse text-left">
                <caption className="sr-only">Roadbook: kilómetros, indicaciones y paradas</caption>
                <thead>
                  <tr className="font-mono text-[11px] font-semibold tracking-[0.1em] text-muted">
                    <th scope="col" className="w-14 border-b-2 border-ink py-2 pr-2 font-semibold lg:w-20">
                      TOTAL
                    </th>
                    <th scope="col" className="w-12 border-b-2 border-ink py-2 pr-2 font-semibold lg:w-16">
                      PARC.
                    </th>
                    <th scope="col" className="w-12 border-b-2 border-ink py-2 lg:w-16">
                      <span className="sr-only">Viñeta</span>
                    </th>
                    <th scope="col" className="border-b-2 border-ink py-2 pl-3 font-semibold">
                      INDICACIÓN
                    </th>
                    <th scope="col" className="w-12 border-b-2 border-ink py-2 print:hidden">
                      <span className="sr-only">Quitar</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => {
                    const level = row.partialKm !== null ? legLevel(row.partialKm, autonomyKm) : "ok";
                    const key = row.kind === "stop" ? stationKey(row.station) : row.kind;
                    return (
                      <tr key={key} className="border-b border-rule align-middle">
                        <td className="py-3 pr-2 font-mono text-[17px] font-semibold lg:text-lg">
                          {formatKm(row.totalKm)}
                        </td>
                        <td className="py-3 pr-2 font-mono text-sm text-muted">
                          {row.partialKm === null ? "—" : formatKm(row.partialKm)}
                        </td>
                        <td className="border-x border-rule py-2">
                          <Tulip kind={row.kind} />
                        </td>
                        <td className="py-3 pl-3">
                          {row.kind === "stop" ? (
                            <>
                              <div className="text-[15px] font-bold lg:text-[17px]">
                                Repostar · {formatStationName(row.station.name)}
                                {row.station.town ? `, ${formatStationName(row.station.town)}` : ""}
                              </div>
                              <div className="text-[13px] text-muted lg:text-sm">
                                {[
                                  detourText(detours.get(stationKey(row.station))),
                                  formatSchedule(row.station.schedule),
                                ]
                                  .filter(Boolean)
                                  .join(" · ")}
                                {" · "}
                                <span className="font-mono font-semibold text-ink">
                                  {formatPrice(row.station.price)}
                                </span>{" "}
                                €/L
                                {(row.station as PricedStation).list_price != null ? " con tu descuento" : ""}
                              </div>
                            </>
                          ) : (
                            <div className="text-[15px] font-bold lg:text-[17px]">
                              {row.kind === "start" ? "Salida" : "Llegada"} · {row.place}
                            </div>
                          )}
                          {level !== "ok" && row.partialKm !== null ? (
                            <div className="mt-1 flex items-start gap-1.5 text-[13px] font-semibold">
                              <WarningIcon size={15} className="mt-px shrink-0 text-warn" />
                              {formatKm(row.partialKm)} km desde el repostaje anterior:{" "}
                              {level === "critical"
                                ? "más que tu autonomía"
                                : "cerca del límite de tu autonomía"}{" "}
                              ({autonomyKm} km)
                            </div>
                          ) : null}
                        </td>
                        <td className="py-2 print:hidden">
                          {row.kind === "stop" ? (
                            <button
                              type="button"
                              aria-label={`Quitar la parada de ${formatStationName(row.station.name)}`}
                              onClick={() => stops.toggle(row.station)}
                              className="inline-flex size-11 items-center justify-center rounded-field border-[1.5px] border-rule hover:bg-rule-soft"
                            >
                              <CloseIcon size={16} />
                            </button>
                          ) : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <Link href={backHref} className="self-start py-2 text-[15px] font-bold print:hidden">
                Añadir o cambiar paradas
              </Link>
            </>
          )}

          <AutonomyCheck
            autonomyKm={autonomyKm}
            onChange={(km) => void setParams({ autonomia: km > 0 ? km : null })}
          />
        </div>

        <aside
          aria-label="Llévatela"
          className="fixed inset-x-0 bottom-0 z-10 flex flex-col gap-2.5 border-t border-rule bg-surface px-4 pt-3 pb-[max(1rem,env(safe-area-inset-bottom))] lg:static lg:z-auto lg:w-[360px] lg:shrink-0 lg:gap-3.5 lg:border-0 lg:bg-transparent lg:p-0 print:hidden"
        >
          <h2 className="m-0 hidden text-xl font-bold lg:block">Llévatela</h2>
          {gmaps.data ? (
            <ButtonLink href={gmaps.data.url} target="_blank" rel="noopener" size="lg" block>
              <NavigateIcon size={20} /> Navegar con Google Maps
            </ButtonLink>
          ) : (
            <Button size="lg" block disabled>
              <NavigateIcon size={20} />{" "}
              {gmaps.isError ? "Google Maps no disponible" : "Preparando Google Maps…"}
            </Button>
          )}
          {gmaps.data && gmaps.data.truncated > 0 ? (
            <p className="m-0 flex items-start gap-1.5 text-[13px]">
              <WarningIcon size={15} className="mt-px shrink-0 text-warn" />
              Google Maps admite 9 paradas: se han dejado fuera las {gmaps.data.truncated} últimas.
            </p>
          ) : null}
          <div className="flex gap-2.5 lg:flex-col">
            <Button
              variant="secondary"
              size="lg"
              className="flex-1 lg:flex-none lg:justify-start"
              onClick={() => void gpx()}
              disabled={!route.data || gpxState === "busy"}
            >
              <DownloadIcon size={18} />
              <span className="lg:hidden">GPX</span>
              <span className="hidden lg:inline">
                {gpxState === "busy" ? "Preparando el GPX…" : "Descargar GPX con las paradas"}
              </span>
            </Button>
            <div className="hidden lg:contents">
              <Button
                variant="secondary"
                size="lg"
                className="lg:justify-start"
                onClick={() => window.print()}
              >
                Imprimir o guardar en PDF
              </Button>
            </div>
            <Button
              variant="secondary"
              size="lg"
              className="flex-1 lg:flex-none lg:justify-start"
              onClick={() => void share()}
            >
              <ShareIcon size={18} />
              <span className="lg:hidden">{shared ? "Copiado" : "Compartir"}</span>
              <span className="hidden lg:inline">
                {shared ? "Enlace copiado" : "Copiar el enlace para el móvil"}
              </span>
            </Button>
          </div>
          {gpxState === "error" ? (
            <p role="alert" className="m-0 text-[13px] font-semibold">
              No se pudo preparar el GPX. Inténtalo de nuevo en un momento.
            </p>
          ) : null}
          {stops.list.length > MAX_GPX_STOPS ? (
            <p className="m-0 text-[13px] text-muted">El GPX incluye las {MAX_GPX_STOPS} primeras paradas.</p>
          ) : null}
          <p className="m-0 hidden items-start gap-2 border-t border-rule pt-3.5 text-sm text-muted lg:flex">
            <WarningIcon size={18} className="mt-0.5 shrink-0 text-warn" />
            Los precios son los del MITECO{fetchedAt ? ` a las ${timeFormat.format(fetchedAt)}` : ""}. Pueden
            cambiar antes de que llegues.
          </p>
        </aside>
      </main>
    </div>
  );
}
