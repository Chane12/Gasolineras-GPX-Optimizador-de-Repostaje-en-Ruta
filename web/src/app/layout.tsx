import type { Metadata, Viewport } from "next";
import { Familjen_Grotesk, IBM_Plex_Mono } from "next/font/google";
import type { ReactNode } from "react";

import { SITE_URL } from "@/lib/site";
import { THEME_COLOR } from "@/lib/theme-colors";

import "./globals.css";

import { Providers } from "./providers";

// Fuentes alojadas en la propia web (next/font): sin llamadas a Google en tiempo de ejecución.
const familjen = Familjen_Grotesk({ subsets: ["latin"], variable: "--font-familjen", display: "swap" });
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["500", "600"],
  variable: "--font-plex-mono",
  display: "swap",
});

const DESCRIPTION =
  "Organiza tu ruta y decide dónde repostar al mejor precio, con los precios oficiales del MITECO.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: "Gasolineras en Ruta",
  description: DESCRIPTION,
  applicationName: "Gasolineras en Ruta",
  openGraph: {
    type: "website",
    locale: "es_ES",
    siteName: "Gasolineras en Ruta",
    title: "Gasolineras en Ruta",
    description: DESCRIPTION,
    url: "/",
  },
  twitter: { card: "summary_large_image", title: "Gasolineras en Ruta", description: DESCRIPTION },
  alternates: { canonical: "/" },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: THEME_COLOR.light },
    { media: "(prefers-color-scheme: dark)", color: THEME_COLOR.dark },
  ],
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="es" className={`${familjen.variable} ${plexMono.variable}`}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
