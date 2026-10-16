import { WarningIcon } from "@/components/icons";
import type { Schemas } from "@/lib/api/client";
import { formatKm } from "@/lib/format";

/** Tramos más largos que la autonomía elegida (radar de la API). Sin tramos peligrosos, lo dice. */
export function AutonomyWarnings({
  segments,
  autonomyKm,
}: {
  segments: readonly Schemas["AutonomySegment"][];
  autonomyKm: number;
}) {
  const risky = segments.filter((s) => s.level !== "safe");
  if (risky.length === 0) {
    return (
      <p className="m-0 text-sm text-muted">
        Con <span className="font-mono">{autonomyKm}</span> km de autonomía no hay tramos largos sin
        gasolinera.
      </p>
    );
  }
  return (
    <ul className="m-0 flex list-none flex-col gap-1.5 p-0" aria-label="Avisos de autonomía">
      {risky.map((s) => (
        <li key={`${s.start_km}-${s.end_km}`} className="flex items-start gap-2 text-sm">
          <WarningIcon size={16} className="mt-0.5 shrink-0 text-warn" />
          <span>
            <b>
              {s.level === "critical" ? "Supera tu autonomía" : "Tramo largo"}:{" "}
              <span className="font-mono">{formatKm(s.gap_km)}</span> km
            </b>{" "}
            sin gasolinera, del km <span className="font-mono">{formatKm(s.start_km)}</span> al{" "}
            <span className="font-mono">{formatKm(s.end_km)}</span>.
          </span>
        </li>
      ))}
    </ul>
  );
}
