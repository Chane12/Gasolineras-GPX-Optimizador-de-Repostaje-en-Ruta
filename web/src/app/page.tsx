import { ServerWarmupNotice } from "@/components/server-warmup-notice";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

import { HomeSearch } from "./home-search";

const STEPS = [
  {
    title: "Elige dónde parar",
    text: "Las más baratas de tu camino, por kilómetro o por precio, con el desvío real.",
  },
  {
    title: "Llévate la hoja de ruta",
    text: "Tus paradas en orden, para consultarla en el móvil o imprimirla.",
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
    <div className="flex min-h-dvh flex-col">
      <SiteHeader>
        <a href="#como-funciona" className="py-3 text-[15px] font-semibold no-underline">
          Cómo funciona
        </a>
      </SiteHeader>

      <main className="mx-auto flex w-full max-w-xl flex-1 flex-col lg:max-w-7xl lg:flex-row lg:items-start lg:gap-14 lg:px-10 lg:py-12">
        <div className="flex flex-col lg:w-[540px] lg:shrink-0">
          <section className="flex flex-col gap-3 px-4 pt-7 pb-5 lg:px-0 lg:pt-0">
            <p className="m-0 font-mono text-xs font-semibold tracking-[0.08em] text-muted">
              PRECIOS OFICIALES DEL MITECO
            </p>
            <h1 className="m-0 text-[38px] leading-[1.02] font-bold tracking-[-0.025em] lg:text-5xl lg:leading-[1.05]">
              Organiza tu ruta y decide dónde repostar.
            </h1>
            <p className="m-0 text-[17px] leading-snug text-muted lg:text-lg">
              Te enseñamos las gasolineras más baratas del camino. Tú eliges las paradas y te llevas la hoja
              de ruta.
            </p>
          </section>

          <div className="flex flex-col gap-3 px-4 lg:px-0">
            <ServerWarmupNotice />
            <HomeSearch />
          </div>
        </div>

        <div className="mt-7 flex min-w-0 flex-1 flex-col gap-7 lg:mt-0">
          <div className="lg:overflow-hidden lg:rounded-card lg:border lg:border-rule">
            <RouteIllustration />
          </div>

          <section id="como-funciona" className="flex flex-col px-4 pb-2 lg:px-0">
            <h2 className="m-0 mb-2.5 text-2xl font-bold tracking-[-0.015em]">Tu viaje, parada a parada</h2>
            <ol className="m-0 grid list-none grid-cols-1 p-0 lg:grid-cols-3 lg:gap-6 lg:border-t-2 lg:border-ink lg:pt-4">
              {STEPS.map((step, index) => (
                <li
                  key={step.title}
                  className={`grid grid-cols-[36px_1fr] gap-x-2.5 py-3.5 lg:block lg:border-0 lg:py-0 ${index === 0 ? "border-t-2 border-ink" : "border-t border-rule"}`}
                >
                  <span className="font-mono text-[13px] font-semibold text-accent">0{index + 1}</span>
                  <div>
                    <h3 className="m-0 text-[17px] font-bold lg:mt-1">{step.title}</h3>
                    <p className="m-0 mt-0.5 text-[15px] leading-snug text-muted">{step.text}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </div>
      </main>

      <SiteFooter />
    </div>
  );
}
