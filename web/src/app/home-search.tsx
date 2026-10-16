"use client";

import { useRouter } from "next/navigation";

import { SearchForm, type SearchSubmission } from "@/components/search-form";
import { saveGpx } from "@/lib/gpx-store";
import { serializeSearch } from "@/lib/search-params";

/** Formulario del inicio: al buscar, la búsqueda pasa a la URL de /ruta (y el GPX, al dispositivo). */
export function HomeSearch() {
  const router = useRouter();

  async function search(submission: SearchSubmission) {
    const { options } = submission;
    if (submission.kind === "gpx") {
      await saveGpx(submission.file);
      router.push(serializeSearch("/ruta", { gpx: true, ...options }));
    } else {
      router.push(
        serializeSearch("/ruta", { origen: submission.origen, destino: submission.destino, ...options }),
      );
    }
  }

  return <SearchForm onSubmit={search} />;
}
