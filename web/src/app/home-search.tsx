"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { SearchForm, type SearchSubmission } from "@/components/search-form";
import { saveGpx } from "@/lib/gpx-store";
import { serializeSearch } from "@/lib/search-params";

/** Formulario del inicio: al buscar, la búsqueda pasa a la URL de /ruta (y el GPX, al dispositivo). */
export function HomeSearch() {
  const router = useRouter();

  async function search(submission: SearchSubmission) {
    const { combustible } = submission;
    if (submission.kind === "gpx") {
      await saveGpx(submission.file);
      router.push(serializeSearch("/ruta", { gpx: true, combustible }));
    } else {
      const { origen, destino } = submission;
      router.push(
        serializeSearch("/ruta", {
          origen: origen.text,
          destino: destino.text,
          origenGeo: origen.point ?? null,
          destinoGeo: destino.point ?? null,
          combustible,
        }),
      );
    }
  }

  return (
    <SearchForm
      onSubmit={search}
      secondaryAction={
        <Link href={serializeSearch("/ruta", { demo: true })} className="py-2.5 text-[15px] font-bold">
          Probar con una ruta de ejemplo
        </Link>
      }
    />
  );
}
