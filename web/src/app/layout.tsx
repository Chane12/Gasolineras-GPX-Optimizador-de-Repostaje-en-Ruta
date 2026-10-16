import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "Gasolineras en Ruta",
  description:
    "Organiza tu ruta y decide dónde repostar al mejor precio, con los precios oficiales del MITECO.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
