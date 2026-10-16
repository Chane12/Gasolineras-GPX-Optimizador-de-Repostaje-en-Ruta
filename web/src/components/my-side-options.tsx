import { MAX_SIDE_DISTANCE_M } from "@/lib/road-side";

/** "Solo las de mi lado" (punto 10d), dentro de las opciones avanzadas. */
export function MySideOptions({
  enabled,
  onChange,
}: {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div>
        <h3 className="m-0 text-[17px] font-bold">Solo las de mi lado</h3>
        <p className="m-0 mt-0.5 text-sm text-muted">
          En autovía, las que quedan a tu izquierda te obligan a cruzar: ir hasta la salida siguiente y
          volver.
        </p>
      </div>
      <label className="flex min-h-11 items-center gap-3 text-[15px]">
        <input
          type="checkbox"
          className="size-5 shrink-0 accent-accent"
          checked={enabled}
          onChange={(e) => onChange(e.target.checked)}
        />
        Ocultar las que quedan al otro lado de la carretera
      </label>
      <p className="m-0 text-[13px] text-muted">
        Solo sabemos el lado de las que están pegadas a la carretera (a menos de {MAX_SIDE_DISTANCE_M} m); a
        las demás se llega por una salida y se mantienen.
      </p>
    </div>
  );
}
