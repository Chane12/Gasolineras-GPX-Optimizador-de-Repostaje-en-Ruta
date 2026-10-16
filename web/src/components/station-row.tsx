import { IconButton } from "@/components/button";
import { Hito } from "@/components/hito";
import { CheckIcon, PlusIcon, WarningIcon } from "@/components/icons";
import { formatPrice, formatShortKm } from "@/lib/format";

export interface StationRowProps {
  name: string;
  kmOnRoute: number;
  price: number;
  town?: string | null;
  /** Texto corto del horario: "24 h", "7–22 h"… */
  schedule?: string | null;
  /** Desvío real ida y vuelta; null si aún no se conoce o no se pudo calcular. */
  detourKm?: number | null;
  /** La más barata de la ruta: etiqueta y precio en azul. */
  cheapest?: boolean;
  /** Precio poco interesante (de las caras): en gris. */
  dimmed?: boolean;
  inPlan: boolean;
  onTogglePlan: () => void;
  /** Si se da, el nombre es un botón que centra el mapa en la gasolinera. */
  onSelect?: () => void;
  /** Línea extra bajo los datos (p. ej. "Cerrada al pasar (≈ 23:40)"); `warn` la marca como aviso. */
  note?: { text: string; warn: boolean } | null;
  /** Al pasar el ratón o el foco por la fila: resalta su placa en el mapa. */
  onHighlight?: (on: boolean) => void;
  highlighted?: boolean;
}

/** Fila del índice de gasolineras: hito · nombre y datos · precio · añadir/quitar parada. */
export function StationRow({
  name,
  kmOnRoute,
  price,
  town,
  schedule,
  detourKm,
  cheapest = false,
  dimmed = false,
  inPlan,
  onTogglePlan,
  onSelect,
  onHighlight,
  highlighted = false,
  note = null,
}: StationRowProps) {
  const details = [town, schedule, detourKm != null ? `desvío ${formatShortKm(detourKm)} km` : null].filter(
    Boolean,
  );
  const priceColor = cheapest ? "text-accent" : dimmed ? "text-muted" : "text-ink";

  return (
    <li
      className={`flex items-center gap-3 border-b border-rule-soft py-2.5 ${
        highlighted ? "-mx-2.5 rounded-field px-2.5 outline-2 -outline-offset-2 outline-ink" : ""
      }`}
      onMouseEnter={onHighlight ? () => onHighlight(true) : undefined}
      onMouseLeave={onHighlight ? () => onHighlight(false) : undefined}
      // Con el teclado (foco visible), no al tocar: en el móvil el toque dejaría la fila marcada.
      onFocus={
        onHighlight
          ? (e) => {
              if ((e.target as HTMLElement).matches(":focus-visible")) onHighlight(true);
            }
          : undefined
      }
      onBlur={onHighlight ? () => onHighlight(false) : undefined}
    >
      <Hito km={kmOnRoute} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-1.5">
          {onSelect ? (
            <button
              type="button"
              onClick={onSelect}
              className="min-h-11 cursor-pointer text-left text-[17px] leading-tight font-bold text-ink hover:underline"
            >
              {name}
              <span className="sr-only">, ver la ficha</span>
            </button>
          ) : (
            <span className="text-[17px] leading-tight font-bold">{name}</span>
          )}
          {cheapest ? (
            <span className="rounded-[3px] bg-accent px-[5px] pt-0.5 pb-px text-[11px] font-bold tracking-wide text-on-accent">
              MÁS BARATA
            </span>
          ) : null}
        </div>
        {details.length > 0 ? <div className="text-sm text-muted">{details.join(" · ")}</div> : null}
        {note ? (
          <div
            className={`flex items-center gap-1 text-[13px] ${note.warn ? "font-semibold text-ink" : "text-muted"}`}
          >
            {note.warn ? <WarningIcon size={14} className="shrink-0 text-warn" /> : null}
            {note.text}
          </div>
        ) : null}
      </div>
      <div className={`font-mono text-[19px] font-semibold ${priceColor}`}>
        {formatPrice(price)}
        <span className="sr-only"> euros por litro</span>
      </div>
      <IconButton
        label={inPlan ? `Quitar ${name} de tus paradas` : `Añadir ${name} a tus paradas`}
        aria-pressed={inPlan}
        tone={inPlan ? "filled" : "outline"}
        icon={inPlan ? <CheckIcon size={18} /> : <PlusIcon size={18} />}
        onClick={onTogglePlan}
      />
    </li>
  );
}
