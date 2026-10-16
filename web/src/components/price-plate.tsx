import { formatPrice } from "@/lib/format";

export type PlateTone = "best" | "suggested" | "expensive";

const tones: Record<PlateTone, { plate: string; tip: string }> = {
  best: { plate: "bg-accent text-on-accent border-accent", tip: "border-t-accent" },
  suggested: { plate: "bg-surface text-ink border-ink", tip: "border-t-ink" },
  expensive: { plate: "bg-surface text-muted border-muted", tip: "border-t-muted" },
};

/** Placa de precio del mapa (marcador). En la lista el precio va como texto, no como placa. */
export function PricePlate({ price, tone = "suggested" }: { price: number; tone?: PlateTone }) {
  const t = tones[tone];
  return (
    <span className="relative inline-flex flex-col items-center">
      <span
        className={`rounded-plate border-[1.5px] px-2 py-0.5 font-mono text-xs leading-5 font-semibold ${t.plate}`}
      >
        <span className="sr-only">{tone === "best" ? "La más barata: " : "Precio: "}</span>
        {formatPrice(price)}
      </span>
      <span
        aria-hidden="true"
        className={`size-0 border-x-[5px] border-t-[6px] border-x-transparent ${t.tip}`}
      />
    </span>
  );
}
