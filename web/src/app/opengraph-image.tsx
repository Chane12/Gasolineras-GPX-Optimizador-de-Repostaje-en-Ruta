import { ImageResponse } from "next/og";

import { OG_COLORS as C } from "@/lib/theme-colors";

export const alt = "Gasolineras en Ruta: organiza tu ruta y decide dónde repostar";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

/** Imagen para compartir el enlace: el hito, el titular y un trozo de ruta con el precio más barato. */
export default function OpenGraphImage() {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        background: C.bg,
        padding: 72,
        color: C.ink,
        fontFamily: "sans-serif",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
        <div
          style={{
            width: 44,
            height: 62,
            display: "flex",
            flexDirection: "column",
            border: `4px solid ${C.ink}`,
            borderRadius: "22px 22px 4px 4px",
            overflow: "hidden",
            background: C.bg,
          }}
        >
          <div style={{ height: 18, background: C.hitoRed }} />
        </div>
        <div style={{ fontSize: 40, fontWeight: 700 }}>Gasolineras en Ruta</div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
        <div style={{ fontSize: 78, fontWeight: 700, letterSpacing: -2, lineHeight: 1.02, maxWidth: 960 }}>
          Organiza tu ruta y decide dónde repostar.
        </div>
        <div style={{ fontSize: 32, color: C.muted }}>
          Las gasolineras más baratas del camino, con los precios oficiales del MITECO.
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
        <div style={{ flex: 1, height: 10, borderRadius: 5, background: C.accent }} />
        <div
          style={{
            display: "flex",
            background: C.accent,
            color: C.onAccent,
            fontSize: 34,
            fontWeight: 700,
            padding: "8px 20px",
            borderRadius: 8,
          }}
        >
          1,599 €/L
        </div>
        <div style={{ flex: 1, height: 10, borderRadius: 5, background: C.accent }} />
      </div>
    </div>,
    size,
  );
}
