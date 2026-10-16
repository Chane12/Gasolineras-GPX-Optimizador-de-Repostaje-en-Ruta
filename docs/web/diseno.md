# Sistema de diseño de la web

Dirección aprobada por el propietario el 2026-10-15 ("vamos bien"). Es la referencia para construir `web/`: si algo de aquí cambia, se cambia primero en este documento.

- **Lienzo con las maquetas** (privado del propietario): https://claude.ai/artifact/HDYpUVSR51qrvub9kdqP2B — página "A + C · Propuesta". La página "Exploración A · B · C" guarda las tres direcciones descartadas.
- **Copia de las maquetas en el repo**: [`maquetas/`](maquetas/). Son HTML con estilos en línea: se abren en el navegador y sirven como referencia exacta de medidas, colores y textos.

## Idea

Una herramienta para **organizar la ruta y decidir dónde repostar**. El usuario elige sus paradas y se lleva una hoja de ruta. La autonomía del vehículo es un extra **opcional**, desactivado por defecto.

Público principal: motoristas. De ahí:
- Se usa al sol y con guantes: contraste alto y objetivos táctiles de al menos 44 px.
- Debe tener carácter propio, sin parecer una plantilla ni una web "hecha por IA". Nada de degradados, emojis, tarjetas con borde lateral de color ni tipografías genéricas como Inter o Roboto.

## Origen de la dirección

Es una mezcla de dos de las tres exploraciones:
- **A · Señal** (carretera española): el azul de las señales de orientación como único color de acción, y el **hito kilométrico** (poste blanco con la cabeza roja) como símbolo propio.
- **C · Atlas** (mapa de carreteras y roadbook de rally): la tipografía, las listas separadas por filetes en lugar de tarjetas, los números en monoespaciada y la hoja de ruta en formato roadbook.

Correcciones del propietario sobre la primera mezcla:
1. Usar la tipografía de C.
2. Quitar el exceso de colores pastel: nada de papel crema, fondos teñidos ni carreteras de colores suaves.
3. Poner en el centro las paradas, con la autonomía como opción.

## Colores

| Token | Claro | Oscuro | Uso |
|---|---|---|---|
| `bg` | `#FFFFFF` | `#121619` | Fondo de página y hojas |
| `surface` | `#FFFFFF` | `#1A1F23` | Hoja deslizable, tarjetas flotantes del mapa |
| `map-land` | `#EFEFEC` | `#121619` | Tierra del mapa |
| `map-contour` | `#E1E1DC` | `#1C2226` | Curvas de nivel |
| `map-road` | `#FFFFFF` con borde `#CFCFC9` | `#2B3237` | Carreteras |
| `map-water` | `#D9DFE2` | `#172128` | Agua |
| `ink` | `#161B1F` | `#ECEEF0` | Texto principal, filetes fuertes, botón secundario |
| `muted` | `#5B636A` | `#A5ADB4` | Texto secundario (contraste AA sobre `bg`) |
| `rule` | `#DADAD6` | `#2B3237` | Bordes y separadores |
| `rule-soft` | `#E6E6E2` | `#262D32` | Separador entre filas |
| `field-border` | `#BDBDB7` | `#4A535A` | Bordes de campos |
| `accent` | `#0B4C94` | `#7FB2EC` | **Único color de acción**: botones primarios, enlaces, ruta, la gasolinera más barata |
| `on-accent` | `#FFFFFF` | `#0B0E10` | Texto sobre `accent` |
| `hito-red` | `#C0392B` | `#D9473A` | **Solo** la cabeza del hito kilométrico |
| `ok` | `#1E8A4C` | `#5CC98A` | Solo el punto de "precios actualizados" |
| `warn` | `#E8A900` | `#F2C14E` | Solo el icono de aviso: autonomía (si el usuario la activa) y precios antiguos. Nunca como fondo |

Reglas:
- Ningún fondo teñido ni pastel. Para destacar se usa tinta, peso tipográfico o el azul.
- El rojo existe solo en el hito.
- Los estados nunca se distinguen solo por el color: siempre van con texto o icono.
- El modo oscuro se activa solo, según el sistema (`prefers-color-scheme`).

## Tipografía

- **Familjen Grotesk** (400, 500, 600, 700) para todo el texto.
- **IBM Plex Mono** (500, 600) para **precios, km, minutos y contadores**, con cifras alineadas.
- Tamaños de referencia en móvil:

  | Elemento | Tamaño y peso |
  |---|---|
  | Titular de inicio | 38 px / 700 / interletrado −0,025 em |
  | Título de pantalla | 24 px / 700 |
  | Nombre de gasolinera | 17 px / 700 |
  | Cuerpo | 15–17 px |
  | Secundario | 13–14 px |
  | Precio en lista | 19 px mono |
  | Precio en ficha | 44 px mono |
  | Etiqueta superior | mono 11 px, mayúsculas, interletrado 0,1 em |
- Formato español: coma decimal (`1,639 €/L`), "km" en minúscula.

## Componentes propios

En código: `web/src/components/` (tokens en `web/src/app/globals.css`). Catálogo vivo en la ruta `/diseno` de la web (oculta a los buscadores). Un test (`web/src/design-tokens.test.ts`) impide colores literales fuera de los tokens y la paleta por defecto de Tailwind, que está desactivada.

- **Hito kilométrico**: poste blanco con la cabeza roja y el km de la ruta en mono, con borde de tinta. Aparece en:
  - el logo;
  - cada gasolinera de la lista (40 px de ancho);
  - las paradas en el mapa y en la barra "Tu ruta";
  - la ficha (48 px).
- **Placa de precio en el mapa**: rectángulo con radio de 4 px y un piquito hacia el punto.
  - La más barata: fondo `accent` y texto blanco.
  - Las sugeridas: fondo blanco con borde de tinta.
  - Las caras: borde y texto `muted`.
- **Fila de gasolinera**, separada por filetes, sin tarjeta: hito, nombre, municipio · horario · desvío, precio en mono y botón de 44 px.
  - Sin añadir: "+" con borde `accent`.
  - Ya añadida: ✓ con fondo `accent`.
  - La más barata lleva la etiqueta "MÁS BARATA" (fondo `accent`).
- **Resumen de cifras**: tres columnas entre un filete fuerte arriba y uno fino abajo (Encontradas · Mejor precio · Ahorro hasta).
- **Pestañas de orden**: texto subrayado (Por km · Por precio · Por desvío), no botones.
- **Barra "Tu ruta"**: fija abajo en móvil, en tinta (clara en modo noche). Dibuja el trayecto con un círculo de origen, los hitos de las paradas y un cuadrado de destino; lleva el número de paradas y el botón "Hoja de ruta".
- **Roadbook (hoja de ruta)**: columnas TOTAL · PARC. · viñeta · INDICACIÓN.
  - Las viñetas son flechas de tulipán de rally.
  - Las filas son salida, cada parada de repostaje (se pueden quitar) y llegada.
  - Encima va el trayecto con los hitos y el ahorro estimado.
- **Autonomía (opcional)**: tarjeta plegada "Comprobar autonomía · opcional". Al activarla, los tramos largos se señalan con el icono `warn` y un texto.
- **Indicador de frescura**: píldora "Precios MITECO · hace N min" con el punto `ok`. Si los precios tienen más de 30 min o más de 24 h, el texto lo dice; lo decide la API (`prices.status`).
- **Botones**:
  - Primario: `accent`, 52–54 px de alto y radio de 10 px.
  - Secundario: borde de tinta de 1,5 px.
  - Los de icono, 44×44 px con `aria-label`.

## Mapa

- Estilo propio y neutro, sobre teselas vectoriales de OpenFreeMap: tierra gris claro, curvas de nivel suaves, carreteras blancas y agua gris azulada. No se usa ningún estilo por defecto, porque haría que la web pareciera "un mapa más".
- La **ruta** es el elemento más fuerte: `accent` de 5 px con un halo blanco.
- Origen: círculo con borde. Destino: cuadrado relleno.
- Nombres de ciudades en mayúsculas con interletrado, como en un atlas.
- Atribución visible: "OpenFreeMap · © OpenMapTiles · © OpenStreetMap" (la licencia de OpenMapTiles también pide citarla). Va encima de la hoja, para que no quede tapada.
- En código: `web/src/lib/map/style.ts`. El estilo lee los colores de los tokens CSS al cargarse y se rehace al cambiar el modo claro/oscuro, así que no hay colores sueltos.
- OpenFreeMap no trae curvas de nivel: en su lugar, los bosques y parques llevan el tono `map-contour`, que da la misma textura suave. Los rótulos del mapa usan Noto Sans (los glifos que sirve OpenFreeMap); Familjen Grotesk queda para la interfaz.

## Textos

- Español cercano y directo, tuteando, con vocabulario de carretera. Ejemplos: "Elige tus paradas", "Tu ruta", "Hoja de ruta", "Añadir parada", "Cómo llegar", "Navegar con Google Maps".
- Sin exclamaciones ni emojis. Los errores explican qué pasa y qué hacer; la API ya devuelve los mensajes en español.

## Flujo aprobado (2026-10-16)

Tras la revisión de experiencia ([`revision-ux.md`](revision-ux.md)), el propietario aprobó **las maquetas del flujo**, que **mandan sobre las de abajo** cuando no coinciden:

- Lienzo: https://claude.ai/artifact/43WPRaqsBAE5mxtKr7moXN (privado del propietario).
- Copia en el repo: [`maquetas/flujo/`](maquetas/flujo/).

| Maqueta | Qué fija |
|---|---|
| `Escritorio-Inicio` | Inicio a dos columnas: formulario reducido (origen, destino, combustible) con sugerencias de lugares; ejemplo visual y los tres pasos |
| `Escritorio-Ruta` | El sitio de trabajo: <ul><li>cabecera con la búsqueda editable;</li><li>panel izquierdo con filtros, resumen, orden, unas 8 recomendadas, "Ver las N gasolineras" y "Tu ruta" fija abajo;</li><li>mapa a la derecha con zoom, leyenda, placas solo en las recomendadas y puntos en las demás;</li><li>la fila con el ratón encima, resaltada también en el mapa.</li></ul> |
| `Escritorio-Ficha` | La ficha sustituye a la lista en el panel: "Volver a la lista", anterior/siguiente por km, precio grande, desvío en km y minutos, horario, "En tus paradas" y "Cómo llegar" |
| `Escritorio-HojaDeRuta` | Roadbook con viñetas de tulipán y quitar parada; a la derecha, Google Maps, GPX, imprimir o PDF, copiar el enlace para el móvil y la autonomía opcional |
| `Movil-Inicio` / `Movil-Error` | Sugerencias al escribir; un lugar no encontrado se avisa en su campo, con alternativas ("¿Quisiste decir…?") |
| `Movil-Resultados` | Mapa + hoja con filtros en fila, orden, recomendadas y la barra "Tu ruta" |
| `Movil-Ficha` / `Movil-HojaDeRuta` | Ficha en hoja sobre el mapa; hoja de ruta con los botones de exportar abajo, al alcance del pulgar |

Reglas nuevas que salen del flujo:
- **Filtros con palabras de conductor**, aplicados al momento: "Hasta N km de desvío", "Solo abiertas 24 h", "Ver también las de paso" (antes "Modo España Vaciada") y "Avisar de mi autonomía". La opción "una cada N km" desaparece: las recomendadas ya incluyen la más barata de cada tramo.
- **Legibilidad**: unas 8 recomendadas a la vista; las demás, detrás de "Ver las N gasolineras" y como puntos sin texto en el mapa.

## Pantallas de referencia

| Maqueta | Qué fija |
|---|---|
| [`D-Inicio`](maquetas/D-Inicio.dc.html) | Cabecera con logo, titular, formulario (origen/destino, GPX, combustible, "Más opciones" plegado), ejemplo de Gredos y los tres puntos de valor |
| [`D-Resultados`](maquetas/D-Resultados.dc.html) | Mapa + hoja deslizable "Elige tus paradas" + barra "Tu ruta" |
| [`D-Gasolinera`](maquetas/D-Gasolinera.dc.html) | Ficha: mapa con el desvío, precio grande, datos y botones "Cómo llegar" / "Añadir parada" |
| [`D-Plan`](maquetas/D-Plan.dc.html) | Hoja de ruta: trayecto, roadbook, autonomía opcional y exportación |
| [`D-Noche`](maquetas/D-Noche.dc.html) | Tokens del modo oscuro |
| [`D-Escritorio`](maquetas/D-Escritorio.dc.html) | Escritorio: buscador en la cabecera, panel con la lista y "Tu ruta", mapa grande |

Las cifras de las maquetas (precios, km, desvíos) son **de ejemplo**: en la web saldrán siempre de la API.
