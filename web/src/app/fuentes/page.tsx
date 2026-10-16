import type { Metadata } from "next";

import { LegalPage } from "@/components/legal-page";

export const metadata: Metadata = {
  title: "Fuentes de datos · Gasolineras en Ruta",
  description:
    "De dónde salen los precios, los mapas y las rutas de Gasolineras en Ruta, y con qué licencia.",
};

export default function SourcesPage() {
  return (
    <LegalPage eyebrow="INFORMACIÓN" title="Fuentes de datos">
      <section className="flex flex-col gap-3">
        <h2>Precios de los carburantes</h2>
        <p>
          Los precios y los datos de cada gasolinera (rótulo, dirección, horario) son los que publica el{" "}
          <a href="https://geoportalgasolineras.es/" target="_blank" rel="noopener">
            Ministerio para la Transición Ecológica y el Reto Demográfico (MITECO)
          </a>
          , que las gasolineras están obligadas a comunicar. Los descargamos cada 30 minutos y la web siempre
          dice de cuándo son. Si el MITECO no responde, usamos la última copia y avisamos de su antigüedad.
        </p>
        <p>
          Los precios pueden cambiar antes de que llegues a la gasolinera: comprueba el surtidor. Los
          descuentos que ves son solo los que tú escribes en «Mis descuentos».
        </p>
      </section>
      <section className="flex flex-col gap-3">
        <h2>Mapas</h2>
        <p>
          Los datos del mapa son de{" "}
          <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">
            OpenStreetMap
          </a>{" "}
          (licencia ODbL, © sus colaboradores), servidos por{" "}
          <a href="https://openfreemap.org" target="_blank" rel="noopener">
            OpenFreeMap
          </a>{" "}
          con el esquema de{" "}
          <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">
            OpenMapTiles
          </a>
          . El estilo del mapa es propio.
        </p>
      </section>
      <section className="flex flex-col gap-3">
        <h2>Lugares y rutas</h2>
        <ul>
          <li>
            Sugerencias de lugares:{" "}
            <a href="https://photon.komoot.io/" target="_blank" rel="noopener">
              Photon
            </a>{" "}
            (komoot), sobre datos de OpenStreetMap.
          </li>
          <li>
            Búsqueda de lugares por nombre:{" "}
            <a href="https://nominatim.org/" target="_blank" rel="noopener">
              Nominatim
            </a>{" "}
            (OpenStreetMap), con Photon de respaldo.
          </li>
          <li>
            Rutas por carretera y desvíos:{" "}
            <a href="https://project-osrm.org/" target="_blank" rel="noopener">
              OSRM
            </a>
            , en sus servidores públicos.
          </li>
        </ul>
        <p>
          Son servicios gratuitos que usamos con moderación (con caché y sin hacer más peticiones de las
          necesarias). Si alguno no responde, la web sigue funcionando con lo que puede.
        </p>
      </section>
    </LegalPage>
  );
}
