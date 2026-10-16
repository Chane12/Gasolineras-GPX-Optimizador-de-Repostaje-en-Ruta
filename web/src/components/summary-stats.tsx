import type { ReactNode } from "react";

export interface Stat {
  label: string;
  value: ReactNode;
  /** Resaltar en azul (p. ej. el mejor precio). */
  accent?: boolean;
}

/** Resumen de cifras entre filetes (Encontradas · Mejor precio · Ahorro hasta). */
export function SummaryStats({ stats }: { stats: Stat[] }) {
  return (
    <dl
      className="grid border-t-2 border-b border-t-ink border-b-rule"
      style={{ gridTemplateColumns: `repeat(${stats.length}, minmax(0, 1fr))` }}
    >
      {stats.map((stat, index) => (
        <div key={stat.label} className={`py-2 ${index > 0 ? "border-l border-rule pl-2.5" : ""}`}>
          <dt className="text-[13px] font-semibold text-muted">{stat.label}</dt>
          <dd className={`m-0 font-mono text-[17px] font-semibold ${stat.accent ? "text-accent" : ""}`}>
            {stat.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}
