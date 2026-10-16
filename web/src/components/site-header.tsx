import Link from "next/link";

/** Logo: el hito kilométrico con el nombre. */
export function Logo() {
  return (
    <span className="inline-flex items-center gap-2.5">
      <svg width="20" height="28" viewBox="0 0 20 28" aria-hidden="true" className="shrink-0">
        <path d="M2 8a8 8 0 0 1 16 0v18H2z" className="fill-hito-body stroke-hito-ink" strokeWidth="2" />
        <path d="M2 8a8 8 0 0 1 16 0v2H2z" className="fill-hito-red" />
        <rect x="6" y="15" width="8" height="2" className="fill-hito-ink" />
        <rect x="6" y="19" width="5" height="2" className="fill-hito-ink" />
      </svg>
      <span className="text-lg font-bold tracking-[-0.01em]">Gasolineras en Ruta</span>
    </span>
  );
}

export function SiteHeader({ children }: { children?: React.ReactNode }) {
  return (
    <header className="flex items-center justify-between gap-4 border-b border-rule px-4 py-3.5">
      <Link href="/" className="text-ink no-underline" aria-label="Gasolineras en Ruta, inicio">
        <Logo />
      </Link>
      {children}
    </header>
  );
}
