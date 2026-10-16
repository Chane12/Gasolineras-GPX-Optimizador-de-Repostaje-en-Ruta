import { formatKm } from "@/lib/format";

type HitoSize = "sm" | "md" | "lg";

const sizes: Record<HitoSize, { box: string; cap: string; number: string }> = {
  sm: {
    box: "w-[30px] rounded-t-[8px] rounded-b-[2px] border-[1.5px]",
    cap: "h-[7px]",
    number: "text-[10px] py-0.5",
  },
  md: {
    box: "w-10 rounded-t-[9px] rounded-b-[2px] border-[1.5px]",
    cap: "h-2.5",
    number: "text-sm py-[5px]",
  },
  lg: {
    box: "w-12 rounded-t-[11px] rounded-b-[3px] border-2",
    cap: "h-[13px]",
    number: "text-base pt-1.5 pb-0.5",
  },
};

/**
 * Hito kilométrico: poste blanco con cabeza roja y el km de la ruta. Símbolo de la marca (docs/web/diseno.md).
 * Mantiene el aspecto de poste también en modo noche.
 */
export function Hito({ km, size = "md" }: { km: number; size?: HitoSize }) {
  const s = sizes[size];
  return (
    <span
      className={`inline-block shrink-0 overflow-hidden border-hito-ink bg-hito-body text-center text-hito-ink ${s.box}`}
    >
      <span aria-hidden="true" className={`block bg-hito-red ${s.cap}`} />
      <span className={`block font-mono leading-none font-semibold ${s.number}`}>
        <span className="sr-only">km </span>
        {formatKm(km)}
      </span>
      {size === "lg" ? (
        <span aria-hidden="true" className="block pb-1 text-[10px] font-bold text-hito-ink/70">
          KM
        </span>
      ) : null}
    </span>
  );
}
