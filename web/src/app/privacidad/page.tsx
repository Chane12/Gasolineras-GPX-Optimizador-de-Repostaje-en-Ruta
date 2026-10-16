import type { Metadata } from "next";

import { LegalPage } from "@/components/legal-page";

export const metadata: Metadata = {
  title: "Privacidad · Gasolineras en Ruta",
  description:
    "Qué datos usa Gasolineras en Ruta y dónde se guardan: sin cuentas, sin cookies y sin seguimiento.",
};

export default function PrivacyPage() {
  return (
    <LegalPage eyebrow="INFORMACIÓN" title="Privacidad">
      <section className="flex flex-col gap-3">
        <h2>En resumen</h2>
        <ul>
          <li>No hay cuentas, no hay cookies y no hay herramientas de seguimiento ni de publicidad.</li>
          <li>Tus paradas y tus ajustes se guardan solo en tu dispositivo.</li>
          <li>Lo que escribes para buscar se usa para calcular la ruta y no se guarda.</li>
        </ul>
      </section>
      <section className="flex flex-col gap-3">
        <h2>Lo que se guarda en tu dispositivo</h2>
        <p>
          La web usa el almacenamiento de tu navegador (no cookies) para recordar, solo ahí: el último archivo
          GPX que subiste, una copia de las paradas que eliges (con el precio de ese momento) y tus ajustes de
          las opciones avanzadas (autonomía, hora de salida, descuentos, marcas que no quieres…). No nos llega
          nada de eso. Puedes borrarlo cuando quieras desde los ajustes de tu navegador.
        </p>
      </section>
      <section className="flex flex-col gap-3">
        <h2>Lo que se envía para buscar</h2>
        <p>
          Para calcular la ruta y las gasolineras, tu navegador envía a nuestro servidor lo que escribes
          (origen y destino) o el archivo GPX, y la ruta resultante. El servidor lo procesa en el momento y no
          lo guarda. Para buscar lugares y calcular rutas, el servidor consulta a Nominatim, Photon y OSRM en
          tu nombre: esos servicios ven las consultas, pero no tu dirección IP.
        </p>
        <p>
          Tu dirección IP solo se usa, en memoria y durante un minuto, para limitar el número de peticiones
          seguidas y evitar abusos. Como cualquier servidor, el de alojamiento puede registrar técnicamente
          las peticiones (dirección IP, fecha y página) durante un tiempo limitado.
        </p>
      </section>
      <section className="flex flex-col gap-3">
        <h2>Servicios de terceros</h2>
        <ul>
          <li>
            El mapa se descarga de OpenFreeMap directamente desde tu navegador, así que OpenFreeMap ve tu
            dirección IP al servirte el mapa.
          </li>
          <li>
            La web se aloja en Vercel y el servidor de búsqueda en Render (en la Unión Europea, Fráncfort).
          </li>
          <li>
            «Navegar con Google Maps» y «Cómo llegar» abren Google Maps con tu ruta solo cuando tú los pulsas;
            a partir de ahí se aplica la privacidad de Google.
          </li>
          <li>Las fuentes tipográficas se sirven desde la propia web, sin llamar a Google.</li>
        </ul>
      </section>
    </LegalPage>
  );
}
