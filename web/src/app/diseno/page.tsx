import type { Metadata } from "next";
import type { ReactNode } from "react";

import { Button, ButtonLink, IconButton } from "@/components/button";
import { FreshnessPill } from "@/components/freshness-pill";
import { Hito } from "@/components/hito";
import { DownloadIcon, NavigateIcon, PlusIcon, ShareIcon } from "@/components/icons";
import { PricePlate } from "@/components/price-plate";
import { SummaryStats } from "@/components/summary-stats";

import { DemoStationList } from "./demo-station-list";

export const metadata: Metadata = {
  title: "Sistema de diseño · Gasolineras en Ruta",
  robots: { index: false, follow: false },
};

// Clases literales (Tailwind solo genera las que ve escritas en el código).
const SWATCHES = [
  { token: "bg", className: "bg-bg" },
  { token: "surface", className: "bg-surface" },
  { token: "ink", className: "bg-ink" },
  { token: "muted", className: "bg-muted" },
  { token: "rule", className: "bg-rule" },
  { token: "field-border", className: "bg-field-border" },
  { token: "accent", className: "bg-accent" },
  { token: "hito-red", className: "bg-hito-red" },
  { token: "ok", className: "bg-ok" },
  { token: "warn", className: "bg-warn" },
  { token: "map-land", className: "bg-map-land" },
  { token: "map-water", className: "bg-map-water" },
];

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-4 border-t-2 border-ink pt-4">
      <h2 className="m-0 text-2xl font-bold tracking-tight">{title}</h2>
      {children}
    </section>
  );
}

export default function DesignSystemPage() {
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-10 px-4 py-10">
      <header className="flex flex-col gap-2">
        <div className="font-mono text-xs font-semibold tracking-[0.1em] text-muted">SISTEMA DE DISEÑO</div>
        <h1 className="m-0 text-[38px] leading-none font-bold tracking-[-0.025em]">Gasolineras en Ruta</h1>
        <p className="m-0 text-muted">
          Componentes y tokens de docs/web/diseno.md. El modo noche sigue al del sistema.
        </p>
      </header>

      <Section title="Colores">
        <ul className="m-0 grid list-none grid-cols-2 gap-3 p-0 sm:grid-cols-4">
          {SWATCHES.map(({ token, className }) => (
            <li key={token} className="flex flex-col gap-1.5">
              <span className={`block h-12 rounded-field border border-rule ${className}`} />
              <span className="font-mono text-xs font-semibold">{token}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Tipografía">
        <p className="m-0 text-[38px] leading-none font-bold tracking-[-0.025em]">
          Organiza tu ruta y decide dónde repostar.
        </p>
        <p className="m-0 text-[17px] text-muted">
          Familjen Grotesk para el texto; IBM Plex Mono para cifras:{" "}
          <span className="font-mono font-semibold text-ink">1,639 €/L · km 118 · 352 km</span>
        </p>
      </Section>

      <Section title="Botones">
        <div className="flex flex-wrap items-center gap-3">
          <Button size="lg">Ver gasolineras de la ruta</Button>
          <ButtonLink href="#" size="lg">
            <NavigateIcon size={20} /> Navegar con Google Maps
          </ButtonLink>
          <Button variant="secondary" size="lg">
            <DownloadIcon size={18} /> Descargar GPX
          </Button>
          <Button variant="secondary">Editar</Button>
          <Button variant="quiet">Usar mi archivo GPX</Button>
          <IconButton label="Añadir a tus paradas" icon={<PlusIcon size={18} />} />
          <IconButton label="Compartir" tone="plain" icon={<ShareIcon size={18} />} />
        </div>
      </Section>

      <Section title="Hito kilométrico y placas de precio">
        <div className="flex flex-wrap items-end gap-6">
          <Hito km={118} size="sm" />
          <Hito km={118} />
          <Hito km={118} size="lg" />
          <PricePlate price={1.639} tone="best" />
          <PricePlate price={1.659} />
          <PricePlate price={1.712} tone="expensive" />
        </div>
      </Section>

      <Section title="Índice de gasolineras">
        <SummaryStats
          stats={[
            { label: "Encontradas", value: "9" },
            { label: "Mejor precio", value: "1,639 €/L", accent: true },
            { label: "Ahorro hasta", value: "0,21 €/L" },
          ]}
        />
        <DemoStationList />
      </Section>

      <Section title="Antigüedad de los precios">
        <div className="flex flex-col items-start gap-2">
          <FreshnessPill status="fresh" ageMinutes={12} />
          <FreshnessPill status="stale" ageMinutes={190} />
          <FreshnessPill status="very_stale" ageMinutes={3000} />
          <FreshnessPill status="loading" ageMinutes={null} />
        </div>
      </Section>

      <p className="m-0 text-xs text-muted">Datos de ejemplo.</p>
    </main>
  );
}
