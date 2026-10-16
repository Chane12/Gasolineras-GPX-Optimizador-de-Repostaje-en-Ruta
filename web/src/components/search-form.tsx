"use client";

import { useQueryClient } from "@tanstack/react-query";
import { type FormEvent, type ReactNode, useId, useRef, useState } from "react";

import { Button } from "@/components/button";
import { ArrowRightIcon, CloseIcon, SwapIcon, UploadIcon, WarningIcon } from "@/components/icons";
import { emptyPlace, PlaceInput, type PlaceValue } from "@/components/place-input";
import { api, type ApiClient } from "@/lib/api/client";
import { type PlaceSuggestion, placeSuggestionsQuery, useFuels } from "@/lib/api/queries";
import { validateGpxFile } from "@/lib/gpx-store";
import { resolvePlace } from "@/lib/place-resolution";
import { DEFAULT_FUEL, type FuelId, type LatLon } from "@/lib/search-params";

/** Un extremo de la ruta: el nombre y, si se conoce, el punto exacto (elegido en las sugerencias). */
export interface RouteEnd {
  text: string;
  point?: LatLon;
}

export type SearchSubmission = (
  { kind: "text"; origen: RouteEnd; destino: RouteEnd } | { kind: "gpx"; file: File }
) & { combustible: FuelId };

type PlaceField = "origen" | "destino";

interface PlaceProblem {
  message: string;
  alternatives: PlaceSuggestion[];
}

const field =
  "h-12 w-full rounded-field border-[1.5px] border-field-border bg-surface px-3 text-[17px] font-semibold text-ink";

function FieldMessage({ id, children }: { id: string; children: ReactNode }) {
  return (
    <div id={id} role="alert" className="flex items-start gap-2 text-[15px] leading-snug">
      <WarningIcon size={18} className="mt-0.5 shrink-0 text-warn" />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

function formatBytes(bytes: number): string {
  return bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`
    : `${Math.ceil(bytes / 1024)} KB`;
}

const toRouteEnd = (value: PlaceValue, place?: PlaceSuggestion): RouteEnd => {
  const chosen = place ?? value.place;
  return chosen
    ? { text: chosen.name, point: { lat: chosen.lat, lon: chosen.lon } }
    : { text: value.text.trim() };
};

const OriginMarker = <span className="size-3.5 rounded-full border-[3px] border-accent" />;
const DestinationMarker = <span className="size-3.5 bg-accent" />;

/**
 * Formulario del inicio (maquetas Escritorio-Inicio, Movil-Inicio y Movil-Error): origen y destino con
 * sugerencias, o un GPX, y el combustible. El resto de opciones se ajusta ya en la pantalla de la ruta.
 */
export function SearchForm({
  onSubmit,
  client = api,
  secondaryAction,
}: {
  onSubmit: (search: SearchSubmission) => void | Promise<void>;
  client?: ApiClient;
  /** Enlace junto a "Usar mi archivo GPX" (la ruta de ejemplo). */
  secondaryAction?: ReactNode;
}) {
  const ids = useId();
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const fuels = useFuels(client);

  const [origen, setOrigen] = useState<PlaceValue>(emptyPlace);
  const [destino, setDestino] = useState<PlaceValue>(emptyPlace);
  const [gpxFile, setGpxFile] = useState<File | null>(null);
  const [combustible, setCombustible] = useState<FuelId>(DEFAULT_FUEL);
  const [problems, setProblems] = useState<Partial<Record<PlaceField, PlaceProblem>>>({});
  const [gpxError, setGpxError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const values = { origen, destino };
  const setters = { origen: setOrigen, destino: setDestino };

  function edit(name: PlaceField, value: PlaceValue) {
    setters[name](value);
    if (problems[name]) setProblems((p) => ({ ...p, [name]: undefined }));
  }

  function pickFile(file: File | undefined) {
    if (!file) return;
    const problem = validateGpxFile(file);
    setGpxError(problem);
    setGpxFile(problem ? null : file);
  }

  async function check(name: PlaceField): Promise<{ end?: RouteEnd; problem?: PlaceProblem }> {
    const value = values[name];
    if (value.text.trim().length < 2) {
      return {
        problem: {
          message: name === "origen" ? "Escribe de dónde sales." : "Escribe a dónde vas.",
          alternatives: [],
        },
      };
    }
    const result = await resolvePlace(value, (text) =>
      queryClient.fetchQuery(placeSuggestionsQuery(text, client)),
    );
    if (result.status === "found") return { end: toRouteEnd(value, result.place) };
    if (result.status === "unchecked") return { end: toRouteEnd(value) };
    const typed = value.text.trim();
    return {
      problem: {
        message:
          result.alternatives.length > 0
            ? `«${typed}» no aparece tal cual. ¿Te refieres a…?`
            : `No encontramos «${typed}». Revisa cómo está escrito o prueba con un pueblo cercano.`,
        alternatives: result.alternatives,
      },
    };
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    try {
      if (gpxFile) {
        await onSubmit({ kind: "gpx", file: gpxFile, combustible });
        return;
      }
      const [o, d] = await Promise.all([check("origen"), check("destino")]);
      setProblems({ origen: o.problem, destino: d.problem });
      if (o.end && d.end) await onSubmit({ kind: "text", origen: o.end, destino: d.end, combustible });
    } finally {
      setSubmitting(false);
    }
  }

  function placeField(name: PlaceField, props: { label: string; marker: ReactNode; placeholder: string }) {
    const problem = problems[name];
    const messageId = `${ids}-${name}-msg`;
    return (
      <div className="flex flex-col gap-2">
        <PlaceInput
          {...props}
          value={values[name]}
          onChange={(v) => edit(name, v)}
          invalid={Boolean(problem)}
          describedBy={problem ? messageId : undefined}
          enterKeyHint={name === "origen" ? "next" : "search"}
          client={client}
        />
        {problem ? (
          <FieldMessage id={messageId}>
            {problem.message}
            {problem.alternatives.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {problem.alternatives.map((place) => (
                  <button
                    key={`${place.name}-${place.lat}-${place.lon}`}
                    type="button"
                    className="flex min-h-11 flex-col items-start justify-center rounded-field border-[1.5px] border-accent px-3.5 py-1 text-left font-bold text-accent hover:bg-rule-soft"
                    onClick={() => edit(name, { text: place.name, place })}
                  >
                    {place.name}
                    {place.context ? (
                      <span className="text-xs font-semibold text-muted">{place.context}</span>
                    ) : null}
                  </button>
                ))}
              </div>
            ) : null}
          </FieldMessage>
        ) : null}
      </div>
    );
  }

  return (
    <form
      noValidate
      onSubmit={handleSubmit}
      aria-label="Buscar gasolineras en tu ruta"
      className="flex flex-col gap-4 rounded-card border-[1.5px] border-ink bg-surface p-4 sm:p-5"
    >
      {gpxFile ? (
        <div className="flex items-center gap-3 rounded-field border-[1.5px] border-field-border p-3">
          <UploadIcon size={20} className="shrink-0 text-accent" />
          <div className="min-w-0 flex-1">
            <div className="truncate font-bold">{gpxFile.name}</div>
            <div className="text-sm text-muted">Tu ruta GPX · {formatBytes(gpxFile.size)}</div>
          </div>
          <Button variant="secondary" onClick={() => setGpxFile(null)}>
            <CloseIcon size={16} /> Quitar
          </Button>
        </div>
      ) : (
        <div className="flex items-start gap-2">
          <div className="flex min-w-0 flex-1 flex-col gap-3.5">
            {placeField("origen", {
              label: "Origen",
              marker: OriginMarker,
              placeholder: "¿De dónde sales?",
            })}
            {placeField("destino", {
              label: "Destino",
              marker: DestinationMarker,
              placeholder: "¿A dónde vas?",
            })}
          </div>
          <button
            type="button"
            aria-label="Intercambiar origen y destino"
            title="Intercambiar origen y destino"
            onClick={() => {
              setOrigen(destino);
              setDestino(origen);
              setProblems({ origen: problems.destino, destino: problems.origen });
            }}
            className="mt-[68px] inline-flex size-11 shrink-0 items-center justify-center rounded-field border-[1.5px] border-rule text-ink hover:bg-rule-soft"
          >
            <SwapIcon size={18} />
          </button>
        </div>
      )}
      {gpxError ? <FieldMessage id={`${ids}-gpx-msg`}>{gpxError}</FieldMessage> : null}

      <label className="flex flex-col gap-1 text-sm font-bold">
        Combustible
        <select
          className={field}
          value={combustible}
          onChange={(e) => setCombustible(e.target.value as FuelId)}
        >
          {fuels.data ? (
            fuels.data.map((fuel) => (
              <option key={fuel.id} value={fuel.id}>
                {fuel.label}
              </option>
            ))
          ) : (
            <option value={DEFAULT_FUEL}>Gasolina 95</option>
          )}
        </select>
      </label>

      <Button type="submit" size="lg" block disabled={submitting}>
        {submitting ? "Buscando…" : "Ver gasolineras de la ruta"}
        {submitting ? null : <ArrowRightIcon size={20} />}
      </Button>

      <div className="-my-1 flex flex-wrap items-center justify-between gap-x-4">
        {gpxFile ? (
          <span />
        ) : (
          <>
            <Button variant="quiet" onClick={() => fileInput.current?.click()}>
              <UploadIcon size={18} /> Usar mi archivo GPX
            </Button>
            <input
              ref={fileInput}
              type="file"
              accept=".gpx,application/gpx+xml"
              className="sr-only"
              tabIndex={-1}
              aria-label="Archivo GPX de tu ruta"
              onChange={(e) => {
                pickFile(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
          </>
        )}
        {secondaryAction}
      </div>
    </form>
  );
}
