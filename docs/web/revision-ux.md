# Revisión de experiencia y flujo (2026-10-16)

Recorrido completo de la web publicada (https://gasolineras-web.vercel.app) como lo haría un usuario, en ordenador (1440 × 900) y móvil (390 × 844), tras el punto 6. El propietario lo pidió porque "queda mucho por pulir a nivel de experiencia y de flujo". Este documento recoge lo que falla y la propuesta de flujo. Las decisiones del propietario se anotan al final y pasan después a [`plan.md`](plan.md).

## Recorrido probado

1. Inicio → "Más opciones".
2. Ávila → Segovia → resultados.
3. "Editar".
4. Lugar mal escrito ("Mdrdddd").
5. Subir un GPX → resultados.
6. `/ruta` sin búsqueda.

## Lo que falla, por gravedad

### Graves: rompen el flujo

| # | Problema | Dónde |
|---|---|---|
| 1 | **El flujo se corta tras elegir paradas**: añades una parada y no pasa nada. No hay "Tu ruta", ni siguiente paso, ni forma de llevarte las paradas. Es la idea central del producto | Resultados |
| 2 | **"Editar" pierde la búsqueda**: vuelve al inicio con el formulario vacío. Cambiar solo el combustible obliga a escribirlo todo otra vez | Resultados → Inicio |
| 3 | **Un lugar mal escrito se descubre tarde y lejos**. Pasa esto: <ul><li>Te lleva a resultados, con el mapa vacío.</li><li>La tarjeta dice "Mdrdddd → Segovia · Buscando gasolineras…", que es mentira porque ya falló.</li><li>El error sale abajo, lejos del campo.</li><li>"Reintentar" repite el mismo fallo.</li></ul>Debería avisarse en el formulario, o mejor, evitarse con sugerencias mientras escribes | Inicio / Resultados |
| 4 | **El inicio promete algo que ya no hay**: "Tu hoja de ruta, sin cobertura… quedan guardadas en el móvil". El modo sin conexión se aplazó | Inicio |
| 5 | **El ordenador no tiene disposición propia**: <ul><li>En el inicio, una columna estrecha.</li><li>En resultados, una lista estirada a 1.400 px, con el precio a un metro del nombre.</li></ul> | Todo |

### Importantes: hacen la experiencia pobre

| # | Problema |
|---|---|
| 6 | En resultados no se puede cambiar nada: ni combustible, ni distancia, ni filtros. Todo está en el inicio, escondido en "Más opciones" |
| 7 | Las opciones usan jerga: "Asegurar una gasolinera cada 50 km", "Cuántas mostrar", "Modo España Vaciada". Las tiene que entender el usuario en el inicio, antes de ver ningún resultado |
| 8 | Faltan cosas en la lista: <ul><li>el resumen (encontradas, mejor precio, ahorro);</li><li>el orden por precio o desvío;</li><li>el desvío real;</li><li>el horario (solo pone "24 h");</li><li>nombres legibles (llegan en mayúsculas del MITECO: "E.S GREDOS")</li></ul> |
| 9 | El ahorro no se entiende: "0,21 €/L" no dice cuánto te ahorras en tu depósito |
| 10 | En el mapa del ordenador no hay botones de zoom (solo la rueda del ratón), y al pasar el ratón por una fila no se ve su placa |
| 11 | Mientras carga, aparecen placas sobre un mapa aún vacío y sin ruta durante un instante |
| 12 | La ruta GPX se llama "Tu ruta GPX" en lugar del nombre del archivo o el de la ruta |
| 13 | Las placas se tapan entre sí en zonas con muchas gasolineras |

### Menores

- "Cómo funciona" en la cabecera lleva a una sección que repite el texto del inicio.
- `/ruta` sin búsqueda se ve correcta, pero es una página pobre.
- El aviso de servidor despertando aparece en el panel de abajo, lejos de la tarjeta de la ruta.

## Propuesta de flujo

La idea: **el inicio solo arranca; la pantalla de resultados es el sitio de trabajo**. Ahí se ajusta la búsqueda, se eligen paradas y se sale con la hoja de ruta, sin volver atrás.

```text
Inicio (origen, destino y combustible; nada más)
   │  sugerencias de lugares al escribir: el error se evita antes de buscar
   ▼
Ruta: el sitio de trabajo
   ├─ Búsqueda siempre editable: barra arriba en el ordenador, tarjeta que se abre en el móvil
   ├─ Filtros junto a la lista, con efecto inmediato: combustible, distancia, abiertas 24 h, "todas las de la ruta"
   ├─ Lista ↔ mapa (ratón, teclado, toque) y ficha de cada gasolinera
   └─ "Tu ruta": paradas elegidas, siempre a la vista, con el ahorro en € y el botón "Hoja de ruta"
   ▼
Hoja de ruta: roadbook, ahorro, imprimir o PDF, Google Maps, GPX
```

Principios:

1. **Cada paso dice cuál es el siguiente.** Con 0 paradas, "Añade tus paradas con +". Con 1 o más, "Ver hoja de ruta".
2. **Nada se pierde**: la búsqueda está en la URL y las paradas se guardan en el dispositivo desde la primera. Al volver, todo sigue ahí.
3. **Los errores se arreglan donde se producen**: el lugar mal escrito, en su campo; la API dormida, con un aviso junto a lo que espera.
4. **El ordenador aprovecha el ancho**: panel con la lista y "Tu ruta" a la izquierda y mapa grande a la derecha (`D-Escritorio`). **El móvil, el pulgar**: hoja deslizable y barra "Tu ruta" abajo.
5. **Opciones con palabras de conductor**: "Solo abiertas 24 h", "Máx. 5 km de desvío", "Enséñame también las que están en la ruta, aunque no sean baratas".

## Decisiones para el propietario

| # | Pregunta | Recomendación |
|---|---|---|
| A | **Sugerencias de lugares al escribir** (como en Google Maps). Nominatim no lo permite; Photon (gratuito, de OpenStreetMap) sí, con uso razonable | Sí, con Photon. Es lo que más errores evita |
| B | **La pantalla de resultados como sitio de trabajo**: búsqueda y filtros editables ahí, y el inicio reducido a origen, destino y combustible | Sí |
| C | **Ahorro en euros**: preguntar, una vez y de forma opcional, cuántos litros sueles repostar (o el depósito) para decir "ahorras ≈ 6 € en esta parada" | Sí, opcional y recordado en el dispositivo |
| D | **Nombres de las opciones**: cambiar "Modo España Vaciada" y similares por frases de conductor | Sí; el agente propone los textos |
| E | **Cuántas gasolineras se muestran**: hoy se elige un número ("5 gasolineras"). Alternativa: mostrar todas las que merecen la pena y ordenarlas, con las mejores arriba | Quitar el número: ordenar y destacar es más claro |

## Cómo afecta al plan

Los puntos 7–9 siguen en el mismo orden, pero con este flujo como guía:

- **7**: resultados como sitio de trabajo, con búsqueda y filtros editables y la disposición de cada tamaño. También el arreglo del texto del inicio (problema 4), en el primer PR.
- **8**: desvíos y ficha.
- **9**: "Tu ruta" y la hoja de ruta.

La decisión A (sugerencias) puede ir en un PR propio dentro del 7. Antes de programar, el agente prepara las maquetas del flujo en los dos tamaños para que el propietario las apruebe.

## Decisiones del propietario (2026-10-16)

| # | Decisión |
|---|---|
| A | **Sí**: sugerencias de lugares al escribir, con Photon |
| B | **Sí**: la pantalla de resultados es el sitio de trabajo, con búsqueda y filtros editables ahí; el inicio, solo origen, destino y combustible |
| C | **No de momento**: el ahorro en euros según los litros que repostas queda como posibilidad futura (`ROADMAP.md`, Fase 4+) |
| D | **Sí**: opciones con frases de conductor, con los textos que proponga el agente |
| E | **Sí, con una condición: que no aparezcan tantas que sea ilegible**. Regla propuesta, a validar con las maquetas: <ul><li>La lista enseña primero las **recomendadas**: la más barata de cada tramo de la ruta y las más baratas en general, unas 8–10 como máximo según la longitud. Debajo, "Ver todas (N)".</li><li>En el mapa, **solo las recomendadas llevan placa de precio**. Las demás son un punto pequeño, sin texto, que se puede tocar.</li><li>Si dos placas se solapan, se queda la más barata.</li></ul> |
