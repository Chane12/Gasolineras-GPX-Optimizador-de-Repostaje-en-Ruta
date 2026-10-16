import Link from "next/link";

/** Pie común: fuentes de los datos y enlaces legales. */
export function SiteFooter({ className = "" }: { className?: string }) {
  return (
    <footer
      className={`flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-rule px-4 pt-3.5 pb-5 text-[13px] leading-normal text-muted lg:px-10 ${className}`}
    >
      <span>
        Precios: Ministerio para la Transición Ecológica · Mapas y rutas © colaboradores de OpenStreetMap
      </span>
      <nav aria-label="Información" className="flex gap-4">
        <Link href="/fuentes" className="font-semibold">
          Fuentes de datos
        </Link>
        <Link href="/privacidad" className="font-semibold">
          Privacidad
        </Link>
      </nav>
    </footer>
  );
}
