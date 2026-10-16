import type { ReactNode } from "react";

import { WarningIcon } from "@/components/icons";
import type { PlaceSuggestion } from "@/lib/api/queries";
import type { PlaceProblem } from "@/lib/use-place-check";

export function FieldMessage({ id, children }: { id: string; children: ReactNode }) {
  return (
    <div id={id} role="alert" className="flex items-start gap-2 text-[15px] leading-snug">
      <WarningIcon size={18} className="mt-0.5 shrink-0 text-warn" />
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}

/** Un lugar que no aparece: el mensaje y las alternativas en botones (maqueta Movil-Error). */
export function PlaceProblemMessage({
  id,
  problem,
  onPick,
}: {
  id: string;
  problem: PlaceProblem;
  onPick: (place: PlaceSuggestion) => void;
}) {
  return (
    <FieldMessage id={id}>
      {problem.message}
      {problem.alternatives.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-2">
          {problem.alternatives.map((place) => (
            <button
              key={`${place.name}-${place.lat}-${place.lon}`}
              type="button"
              className="flex min-h-11 flex-col items-start justify-center rounded-field border-[1.5px] border-accent bg-surface px-3.5 py-1 text-left font-bold text-accent hover:bg-rule-soft"
              onClick={() => onPick(place)}
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
  );
}
