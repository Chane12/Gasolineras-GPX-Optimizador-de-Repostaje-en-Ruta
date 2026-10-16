// Color de la barra del navegador (meta theme-color). Copia de --bg en globals.css: único otro sitio
// con colores literales permitido por el test de tokens.
export const THEME_COLOR = { light: "#ffffff", dark: "#121619" } as const;

// Imagen para compartir (Open Graph): se genera en el servidor y no puede leer variables CSS. Copia de
// --bg, --ink, --muted, --accent y del hito (globals.css).
export const OG_COLORS = {
  bg: "#ffffff",
  ink: "#161b1f",
  muted: "#5b636a",
  accent: "#0b4c94",
  onAccent: "#ffffff",
  hitoRed: "#c0392b",
  land: "#efefec",
} as const;
