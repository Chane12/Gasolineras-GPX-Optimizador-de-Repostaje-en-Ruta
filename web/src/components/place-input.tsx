"use client";

import { type KeyboardEvent, type ReactNode, useEffect, useId, useState } from "react";

import { CloseIcon, PinIcon } from "@/components/icons";
import { api, type ApiClient } from "@/lib/api/client";
import {
  MIN_SUGGEST_CHARS,
  normalizePlace,
  type PlaceSuggestion,
  usePlaceSuggestions,
} from "@/lib/api/queries";

/** Lo escrito y, si se eligió una sugerencia, el lugar exacto (para no volver a buscarlo por nombre). */
export interface PlaceValue {
  text: string;
  place?: PlaceSuggestion;
}

export const emptyPlace: PlaceValue = { text: "" };

const DEBOUNCE_MS = 250;

function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

/**
 * Campo de lugar con sugerencias al escribir (patrón combobox de WAI-ARIA): flechas para moverse,
 * Intro para elegir, Escape para cerrar. Sin sugerencias (o si Photon no responde) es un campo normal.
 */
export function PlaceInput({
  label,
  marker,
  value,
  onChange,
  placeholder,
  invalid = false,
  describedBy,
  enterKeyHint,
  hideLabel = false,
  client = api,
}: {
  label: string;
  /** Símbolo del origen (círculo) o del destino (cuadrado). */
  marker: ReactNode;
  value: PlaceValue;
  onChange: (value: PlaceValue) => void;
  placeholder?: string;
  invalid?: boolean;
  describedBy?: string;
  enterKeyHint?: "next" | "search";
  /** Etiqueta solo para lectores de pantalla (barra compacta de la ruta). */
  hideLabel?: boolean;
  client?: ApiClient;
}) {
  const ids = useId();
  const listId = `${ids}-list`;
  const [focused, setFocused] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [active, setActive] = useState(-1);

  const query = useDebounced(value.place ? "" : value.text, DEBOUNCE_MS);
  const suggestions = usePlaceSuggestions(query, client);
  const options = value.place ? [] : (suggestions.data ?? []);
  const open =
    focused && !dismissed && normalizePlace(value.text).length >= MIN_SUGGEST_CHARS && options.length > 0;

  function choose(place: PlaceSuggestion) {
    onChange({ text: place.name, place });
    setDismissed(true);
    setActive(-1);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (!open) {
      if (event.key === "ArrowDown" && options.length > 0) {
        setDismissed(false);
        setActive(0);
        event.preventDefault();
      }
      return;
    }
    if (event.key === "ArrowDown") {
      setActive((i) => (i + 1) % options.length);
      event.preventDefault();
    } else if (event.key === "ArrowUp") {
      setActive((i) => (i <= 0 ? options.length - 1 : i - 1));
      event.preventDefault();
    } else if (event.key === "Enter" && active >= 0) {
      const place = options[active];
      if (place) choose(place);
      event.preventDefault();
    } else if (event.key === "Escape") {
      setDismissed(true);
      event.preventDefault();
    }
  }

  return (
    <div className="relative flex flex-col gap-1">
      <label htmlFor={`${ids}-input`} className={hideLabel ? "sr-only" : "text-sm font-bold"}>
        {label}
      </label>
      <div
        className={`flex h-12 items-center gap-2.5 rounded-field border-[1.5px] bg-surface pr-1 pl-3 focus-within:border-accent ${
          invalid ? "border-2 border-ink" : "border-field-border"
        }`}
      >
        <span aria-hidden="true" className="flex shrink-0">
          {marker}
        </span>
        <input
          id={`${ids}-input`}
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={open && active >= 0 ? `${ids}-opt-${active}` : undefined}
          aria-invalid={invalid || undefined}
          aria-describedby={describedBy}
          className="h-full min-w-0 flex-1 bg-transparent text-[17px] font-semibold text-ink outline-none placeholder:font-normal placeholder:text-muted"
          value={value.text}
          placeholder={placeholder}
          autoComplete="off"
          spellCheck={false}
          enterKeyHint={enterKeyHint}
          onChange={(e) => {
            onChange({ text: e.target.value });
            setDismissed(false);
            setActive(-1);
          }}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onKeyDown={onKeyDown}
        />
        {value.place?.context ? (
          <span className="hidden max-w-[45%] shrink truncate text-[13px] text-muted sm:block">
            {value.place.context}
          </span>
        ) : null}
        {value.text ? (
          <button
            type="button"
            aria-label={`Borrar ${label.toLowerCase()}`}
            className="inline-flex size-10 shrink-0 items-center justify-center rounded-field text-muted hover:bg-rule-soft hover:text-ink"
            onClick={() => onChange(emptyPlace)}
          >
            <CloseIcon size={16} />
          </button>
        ) : null}
      </div>
      <ul
        id={listId}
        role="listbox"
        aria-label={`Sugerencias de ${label.toLowerCase()}`}
        hidden={!open}
        className="absolute inset-x-0 top-full z-20 m-0 mt-1.5 list-none overflow-hidden rounded-card border border-rule bg-surface p-0 shadow-float"
      >
        {options.map((place, index) => (
          <li
            key={`${place.name}-${place.lat}-${place.lon}`}
            id={`${ids}-opt-${index}`}
            role="option"
            aria-selected={index === active}
            className={`flex min-h-13 cursor-pointer items-center gap-3 border-b border-rule-soft px-3.5 py-1.5 last:border-b-0 hover:bg-rule-soft ${
              index === active ? "outline-2 -outline-offset-2 outline-accent" : ""
            }`}
            // mousedown: elegir antes de que el campo pierda el foco.
            onMouseDown={(e) => {
              e.preventDefault();
              choose(place);
            }}
          >
            <PinIcon size={16} className="shrink-0 text-muted" />
            <span className="min-w-0">
              <span className="block truncate text-base font-bold">{place.name}</span>
              {place.context ? (
                <span className="block truncate text-[13px] text-muted">{place.context}</span>
              ) : null}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
