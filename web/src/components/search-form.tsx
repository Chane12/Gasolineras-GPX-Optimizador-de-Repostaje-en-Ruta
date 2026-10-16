"use client";

import { type FormEvent, useId, useRef, useState } from "react";

import { Button } from "@/components/button";
import {
  ArrowRightIcon,
  ChevronDownIcon,
  CloseIcon,
  SwapIcon,
  UploadIcon,
  WarningIcon,
} from "@/components/icons";
import { api, type ApiClient } from "@/lib/api/client";
import { useFuels } from "@/lib/api/queries";
import { validateGpxFile } from "@/lib/gpx-store";
import { DEFAULT_FUEL, type FuelId, LIMITS } from "@/lib/search-params";

export interface SearchOptions {
  combustible: FuelId;
  radio: number;
  top: number;
  /** 0 = sin "más barata por tramo". */
  tramo: number;
  abierta24h: boolean;
  vaciada: boolean;
  /** 0 = sin aviso de autonomía. */
  autonomia: number;
}

export type SearchSubmission = (
  { kind: "text"; origen: string; destino: string } | { kind: "gpx"; file: File }
) & { options: SearchOptions };

const RADIO_CHOICES = [1, 2, 3, 5, 8, 10, 15];
const TOP_CHOICES = [3, 5, 10, 15, 20];
const TRAMO_CHOICES = [0, 30, 50, 100, 150, 200, 300];
const PROFILES = [
  { id: "moto", label: "Moto", km: 250 },
  { id: "coche", label: "Coche", km: 600 },
  { id: "gran", label: "Gran autonomía", km: 900 },
  { id: "otra", label: "Otra", km: null },
] as const;
type ProfileId = (typeof PROFILES)[number]["id"];

const field =
  "h-12 w-full rounded-field border-[1.5px] border-field-border bg-surface px-3 text-[17px] text-ink " +
  "aria-invalid:border-ink";
const label = "flex flex-col gap-1 text-sm font-semibold";

function FieldError({ id, message }: { id: string; message: string | undefined }) {
  if (!message) return null;
  return (
    <p id={id} className="m-0 flex items-start gap-1.5 text-sm font-semibold">
      <WarningIcon size={16} className="mt-px shrink-0 text-warn" />
      {message}
    </p>
  );
}

function formatBytes(bytes: number): string {
  return bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`
    : `${Math.ceil(bytes / 1024)} KB`;
}

/**
 * Formulario de búsqueda del inicio (maqueta D-Inicio): origen/destino o GPX, combustible y "Más opciones"
 * plegadas (la autonomía es opcional y está desactivada por defecto).
 */
export function SearchForm({
  onSubmit,
  client = api,
}: {
  onSubmit: (search: SearchSubmission) => void | Promise<void>;
  client?: ApiClient;
}) {
  const ids = useId();
  const fileInput = useRef<HTMLInputElement>(null);
  const fuels = useFuels(client);

  const [origen, setOrigen] = useState("");
  const [destino, setDestino] = useState("");
  const [gpxFile, setGpxFile] = useState<File | null>(null);
  const [combustible, setCombustible] = useState<FuelId>(DEFAULT_FUEL);
  const [radio, setRadio] = useState<number>(LIMITS.radioKm.default);
  const [top, setTop] = useState<number>(LIMITS.top.default);
  const [tramo, setTramo] = useState<number>(LIMITS.tramoKm.default);
  const [abierta24h, setAbierta24h] = useState(false);
  const [vaciada, setVaciada] = useState(false);
  const [autonomyOn, setAutonomyOn] = useState(false);
  const [profile, setProfile] = useState<ProfileId>("moto");
  const [customKm, setCustomKm] = useState("");
  const [errors, setErrors] = useState<Partial<Record<"origen" | "destino" | "gpx" | "autonomia", string>>>(
    {},
  );
  const [submitting, setSubmitting] = useState(false);

  const chosenProfile = PROFILES.find((p) => p.id === profile);
  const autonomia = !autonomyOn ? 0 : (chosenProfile?.km ?? Number.parseInt(customKm, 10));

  const optionsSummary = [
    `Hasta ${radio} km de la ruta`,
    autonomyOn && Number.isFinite(autonomia) && autonomia > 0
      ? `autonomía ${autonomia} km`
      : "aviso de autonomía desactivado",
    abierta24h ? "solo 24 h" : null,
  ]
    .filter(Boolean)
    .join(" · ");

  function pickFile(file: File | undefined) {
    if (!file) return;
    const problem = validateGpxFile(file);
    setErrors((e) => ({ ...e, gpx: problem ?? undefined }));
    setGpxFile(problem ? null : file);
  }

  function validate(): typeof errors {
    const found: typeof errors = {};
    if (!gpxFile) {
      if (origen.trim().length < 2) found.origen = "Escribe de dónde sales.";
      if (destino.trim().length < 2) found.destino = "Escribe a dónde vas.";
    }
    if (
      autonomyOn &&
      (!Number.isFinite(autonomia) ||
        autonomia < LIMITS.autonomiaKm.min ||
        autonomia > LIMITS.autonomiaKm.max)
    ) {
      found.autonomia = `Indica tu autonomía en km (entre ${LIMITS.autonomiaKm.min} y ${LIMITS.autonomiaKm.max}).`;
    }
    return found;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const found = validate();
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    const options: SearchOptions = { combustible, radio, top, tramo, abierta24h, vaciada, autonomia };
    setSubmitting(true);
    try {
      await onSubmit(
        gpxFile
          ? { kind: "gpx", file: gpxFile, options }
          : { kind: "text", origen: origen.trim(), destino: destino.trim(), options },
      );
    } finally {
      setSubmitting(false);
    }
  }

  const err = (name: keyof typeof errors) => ({
    "aria-invalid": errors[name] ? true : undefined,
    "aria-describedby": errors[name] ? `${ids}-${name}-error` : undefined,
  });

  return (
    <form
      noValidate
      onSubmit={handleSubmit}
      aria-label="Buscar gasolineras en tu ruta"
      className="flex flex-col gap-3.5 rounded-card border-[1.5px] border-ink bg-surface p-4"
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
        <div className="flex items-stretch gap-2.5">
          <div aria-hidden="true" className="flex w-3.5 flex-col items-center pt-9 pb-8">
            <span className="size-3 rounded-full border-[3px] border-accent" />
            <span className="my-1 w-0 flex-1 border-l-2 border-dotted border-muted" />
            <span className="size-3 bg-accent" />
          </div>
          <div className="flex flex-1 flex-col gap-2.5">
            <label className={label}>
              Origen
              <input
                className={field}
                value={origen}
                onChange={(e) => setOrigen(e.target.value)}
                placeholder="¿De dónde sales?"
                autoComplete="off"
                enterKeyHint="next"
                {...err("origen")}
              />
            </label>
            <FieldError id={`${ids}-origen-error`} message={errors.origen} />
            <label className={label}>
              Destino
              <input
                className={field}
                value={destino}
                onChange={(e) => setDestino(e.target.value)}
                placeholder="¿A dónde vas?"
                autoComplete="off"
                enterKeyHint="search"
                {...err("destino")}
              />
            </label>
            <FieldError id={`${ids}-destino-error`} message={errors.destino} />
          </div>
          <button
            type="button"
            aria-label="Intercambiar origen y destino"
            title="Intercambiar origen y destino"
            onClick={() => {
              setOrigen(destino);
              setDestino(origen);
            }}
            className="mt-5 inline-flex size-11 shrink-0 items-center justify-center self-center rounded-field border-[1.5px] border-rule text-ink hover:bg-rule-soft"
          >
            <SwapIcon size={18} />
          </button>
        </div>
      )}

      {!gpxFile ? (
        <div>
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
        </div>
      ) : null}
      <FieldError id={`${ids}-gpx-error`} message={errors.gpx} />

      <label className={label}>
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

      <details className="group border-y border-rule">
        <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 py-1.5 [&::-webkit-details-marker]:hidden">
          <span className="flex flex-col">
            <span className="text-[15px] font-bold">Más opciones</span>
            <span className="text-[13px] text-muted">{optionsSummary}</span>
          </span>
          <ChevronDownIcon size={18} className="shrink-0 transition-transform group-open:rotate-180" />
        </summary>

        <div className="flex flex-col gap-3.5 pt-2 pb-4">
          <div className="grid grid-cols-2 gap-3">
            <label className={label}>
              Distancia a la ruta
              <select className={field} value={radio} onChange={(e) => setRadio(Number(e.target.value))}>
                {RADIO_CHOICES.map((km) => (
                  <option key={km} value={km}>
                    Hasta {km} km
                  </option>
                ))}
              </select>
            </label>
            <label className={label}>
              Cuántas mostrar
              <select className={field} value={top} onChange={(e) => setTop(Number(e.target.value))}>
                {TOP_CHOICES.map((n) => (
                  <option key={n} value={n}>
                    {n} gasolineras
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label className={label}>
            Asegurar una gasolinera cada
            <select className={field} value={tramo} onChange={(e) => setTramo(Number(e.target.value))}>
              {TRAMO_CHOICES.map((km) => (
                <option key={km} value={km}>
                  {km === 0 ? "No hace falta" : `${km} km`}
                </option>
              ))}
            </select>
          </label>

          <label className="flex min-h-11 items-center gap-3 text-[15px]">
            <input
              type="checkbox"
              className="size-5 shrink-0 accent-accent"
              checked={abierta24h}
              onChange={(e) => setAbierta24h(e.target.checked)}
            />
            Solo gasolineras abiertas 24 h
          </label>
          <label className="flex min-h-11 items-start gap-3 text-[15px]">
            <input
              type="checkbox"
              className="mt-0.5 size-5 shrink-0 accent-accent"
              checked={vaciada}
              onChange={(e) => setVaciada(e.target.checked)}
            />
            <span>
              Modo España Vaciada
              <span className="block text-[13px] text-muted">
                Todas las gasolineras pegadas a la ruta, aunque no sean las más baratas.
              </span>
            </span>
          </label>

          <fieldset className="m-0 flex flex-col gap-3 border-0 border-t border-rule p-0 pt-3">
            <legend className="sr-only">Aviso de autonomía</legend>
            <label className="flex min-h-11 items-start gap-3 text-[15px]">
              <input
                type="checkbox"
                className="mt-0.5 size-5 shrink-0 accent-accent"
                checked={autonomyOn}
                onChange={(e) => setAutonomyOn(e.target.checked)}
              />
              <span>
                Avisarme de tramos más largos que mi autonomía
                <span className="block text-[13px] text-muted">
                  Opcional. Te marcamos dónde podrías quedarte seco.
                </span>
              </span>
            </label>
            {autonomyOn ? (
              <div className="flex flex-col gap-2.5 pl-8">
                <div role="radiogroup" aria-label="Tu vehículo" className="grid grid-cols-2 gap-1.5">
                  {PROFILES.map((p) => (
                    <label
                      key={p.id}
                      className={`flex min-h-14 cursor-pointer flex-col items-center justify-center rounded-field border-[1.5px] px-2 text-center has-checked:border-2 has-checked:border-accent has-checked:text-accent ${
                        profile === p.id ? "" : "border-field-border"
                      }`}
                    >
                      <input
                        type="radio"
                        name={`${ids}-profile`}
                        className="sr-only"
                        checked={profile === p.id}
                        onChange={() => setProfile(p.id)}
                      />
                      <span className="text-sm font-bold">{p.label}</span>
                      <span className="font-mono text-xs font-semibold">
                        {p.km ? `${p.km} km` : "elige km"}
                      </span>
                    </label>
                  ))}
                </div>
                {profile === "otra" ? (
                  <label className={label}>
                    Tu autonomía (km)
                    <input
                      className={field}
                      inputMode="numeric"
                      value={customKm}
                      onChange={(e) => setCustomKm(e.target.value.replace(/\D/g, ""))}
                      placeholder="Por ejemplo, 320"
                      {...err("autonomia")}
                    />
                  </label>
                ) : null}
                <FieldError id={`${ids}-autonomia-error`} message={errors.autonomia} />
              </div>
            ) : null}
          </fieldset>
        </div>
      </details>

      <Button type="submit" size="lg" block disabled={submitting}>
        {submitting ? "Buscando…" : "Ver gasolineras de la ruta"}
        {submitting ? null : <ArrowRightIcon size={20} />}
      </Button>
    </form>
  );
}
