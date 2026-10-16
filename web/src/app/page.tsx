import Link from "next/link";

import { ServerWarmupNotice } from "@/components/server-warmup-notice";
import { SiteHeader } from "@/components/site-header";
import { serializeSearch } from "@/lib/search-params";

import { HomeSearch } from "./home-search";

const STEPS = [
  {
    title: "Elige dónde parar",
    text: "Las gasolineras de tu camino, por kilómetro o por precio, con el desvío real.",
  },
  {
    title: "Tu hoja de ruta, sin cobertura",
    text: "Las paradas quedan guardadas en el móvil para consultarlas en mitad del puerto.",
  },
  {
    title: "Al navegador, en un toque",
    text: "Abre la ruta con tus paradas en Google Maps o descarga el GPX para tu GPS.",
  },
];

/** Ilustración del inicio: un trozo de mapa con la ruta, un hito y el precio más barato. Decorativa. */
function RouteIllustration() {
  return (
    <svg
      viewBox="0 0 390 140"
      className="block h-auto w-full"
      aria-hidden="true"
      preserveAspectRatio="xMidYMid slice"
    >
      <rect width="390" height="140" className="fill-map-land" />
      <g fill="none" className="stroke-map-contour" strokeWidth="1.2">
        <path d="M-10 26 C 70 6, 140 56, 220 36 S 330 6, 400 36" />
        <path d="M-10 48 C 70 28, 140 78, 220 58 S 330 28, 400 58" />
        <path d="M-10 104 C 90 84, 160 134, 250 114 S 340 94, 400 124" />
      </g>
      <path
        d="M0 92 C 80 86, 150 116, 230 96 S 350 76, 390 88"
        fill="none"
        className="stroke-map-road"
        strokeWidth="6"
      />
      <path
        d="M20 116 C 90 96, 120 56, 200 66 S 320 36, 372 26"
        fill="none"
        className="stroke-bg"
        strokeWidth="10"
        strokeLinecap="round"
      />
      <path
        d="M20 116 C 90 96, 120 56, 200 66 S 320 36, 372 26"
        fill="none"
        className="stroke-accent"
        strokeWidth="4.5"
        strokeLinecap="round"
      />
      <circle cx="20" cy="116" r="6" className="fill-bg stroke-accent" strokeWidth="3" />
      <rect x="366" y="20" width="12" height="12" className="fill-accent stroke-bg" strokeWidth="2" />
      <path
        d="M186 44 a 12 12 0 0 1 24 0 v 20 h -24 z"
        className="fill-hito-body stroke-hito-ink"
        strokeWidth="2"
      />
      <path d="M186 44 a 12 12 0 0 1 24 0 z" className="fill-hito-red" />
      <rect x="216" y="22" width="52" height="24" rx="4" className="fill-accent" />
      <text x="242" y="38" textAnchor="middle" className="fill-on-accent font-mono text-xs font-semibold">
        1,639
      </text>
    </svg>
  );
}

export default function Home() {
  return (
    <div className="mx-auto flex min-h-dvh max-w-xl flex-col">
      <SiteHeader>
        <a href="#como-funciona" className="py-3 text-[15px] font-semibold no-underline">
          Cómo funciona
        </a>
      </SiteHeader>

      <main className="flex flex-1 flex-col">
        <section className="flex flex-col gap-3 px-4 pt-7 pb-5">
          <p className="m-0 font-mono text-xs font-semibold tracking-[0.08em] text-muted">
            PRECIOS OFICIALES DEL MITECO
          </p>
          <h1 className="m-0 text-[38px] leading-[1.02] font-bold tracking-[-0.025em]">
            Organiza tu ruta y decide dónde repostar.
          </h1>
          <p className="m-0 text-[17px] leading-snug text-muted">
            Te enseñamos las gasolineras más baratas del camino. Tú eliges las paradas y te llevas la hoja de
            ruta.
          </p>
        </section>

        <div className="flex flex-col gap-3 px-4">
          <ServerWarmupNotice />
          <HomeSearch />
          <Link
            href={serializeSearch("/ruta", { demo: true })}
            className="self-center py-1.5 text-[15px] font-semibold"
          >
            o prueba con una ruta por la Sierra de Gredos
          </Link>
        </div>

        <div className="mt-7">
          <RouteIllustration />
        </div>

        <section id="como-funciona" className="flex flex-col px-4 pt-6 pb-2">
          <h2 className="m-0 mb-2.5 text-2xl font-bold tracking-[-0.015em]">Tu viaje, parada a parada</h2>
          <ol className="m-0 list-none p-0">
            {STEPS.map((step, index) => (
              <li
                key={step.title}
                className={`grid grid-cols-[36px_1fr] gap-x-2.5 py-3.5 ${index === 0 ? "border-t-2 border-ink" : "border-t border-rule"}`}
              >
                <span className="font-mono text-[13px] font-semibold text-accent">0{index + 1}</span>
                <div>
                  <h3 className="m-0 text-[17px] font-bold">{step.title}</h3>
                  <p className="m-0 mt-0.5 text-[15px] leading-snug text-muted">{step.text}</p>
                </div>
              </li>
            ))}
          </ol>
        </section>
      </main>

      <footer className="border-t border-rule px-4 pt-3.5 pb-5 text-[13px] leading-normal text-muted">
        Precios: Ministerio para la Transición Ecológica · Mapas y rutas © colaboradores de OpenStreetMap
      </footer>
    </div>
  );
}
