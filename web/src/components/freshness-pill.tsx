import { WarningIcon } from "@/components/icons";
import { formatAge } from "@/lib/format";

/** Estado de los precios tal como lo devuelve la API (`PricesStatus.status`). */
export type PricesFreshness = "fresh" | "stale" | "very_stale" | "loading" | "unavailable";

function message(status: PricesFreshness, ageMinutes: number | null): string {
  const age = ageMinutes != null ? formatAge(ageMinutes) : null;
  switch (status) {
    case "fresh":
      return age ? `Precios MITECO · hace ${age}` : "Precios MITECO actualizados";
    case "stale":
      return `Precios de hace ${age ?? "un rato"}`;
    case "very_stale":
      return `Precios de hace ${age ?? "más de un día"}: pueden no estar al día`;
    case "loading":
      return "Cargando precios…";
    case "unavailable":
      return "Precios no disponibles ahora mismo";
  }
}

/**
 * Píldora de antigüedad de los precios. Siempre visible: es un invariante del proyecto
 * (nunca mostrar precios sin decir de cuándo son). Aviso más fuerte cuanto más antiguos.
 */
export function FreshnessPill({
  status,
  ageMinutes,
}: {
  status: PricesFreshness;
  ageMinutes: number | null;
}) {
  const warning = status === "stale" || status === "very_stale" || status === "unavailable";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border bg-surface py-1 pr-3 pl-2 text-[13px] ${
        status === "very_stale" ? "border-ink font-bold" : "border-rule font-semibold"
      }`}
    >
      {warning ? (
        <WarningIcon size={14} className="text-warn" />
      ) : (
        <span
          aria-hidden="true"
          className={`size-2 rounded-full ${status === "fresh" ? "bg-ok" : "bg-muted"}`}
        />
      )}
      {message(status, ageMinutes)}
    </span>
  );
}
