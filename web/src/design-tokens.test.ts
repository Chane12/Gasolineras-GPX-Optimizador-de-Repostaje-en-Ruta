/**
 * Guardián del sistema de diseño (docs/web/diseno.md): los colores solo existen como tokens.
 * Falla si aparece un color literal fuera de los archivos permitidos o una clase de la paleta por
 * defecto de Tailwind (que está desactivada y no generaría nada).
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(__dirname);
const ALLOWED_LITERAL_COLORS = new Set(["app/globals.css", "lib/theme-colors.ts"]);
const SOURCE = /\.(tsx?|css)$/;

const HEX_COLOR = /#[0-9a-fA-F]{3,8}\b/g;
const CSS_COLOR_FN = /\b(?:rgba?|hsla?|oklch|oklab)\(\s*\d/g;
const TAILWIND_PALETTE =
  /\b(?:bg|text|border|ring|fill|stroke|outline|decoration|from|to|via|shadow)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|black|white)(?:-\d{2,3})?\b/g;

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return SOURCE.test(name) && !name.endsWith(".test.ts") && !name.endsWith(".test.tsx") ? [path] : [];
  });
}

describe("design tokens", () => {
  const files = sourceFiles(SRC).map((path) => ({
    path: relative(SRC, path),
    text: readFileSync(path, "utf8"),
  }));

  it("finds the source files", () => {
    expect(files.length).toBeGreaterThan(3);
  });

  it("has no literal colours outside the token files", () => {
    const offenders = files
      .filter((f) => !ALLOWED_LITERAL_COLORS.has(f.path))
      .flatMap((f) =>
        [...(f.text.match(HEX_COLOR) ?? []), ...(f.text.match(CSS_COLOR_FN) ?? [])].map(
          (m) => `${f.path}: ${m}`,
        ),
      );
    expect(offenders).toEqual([]);
  });

  it("does not use Tailwind's default palette", () => {
    const offenders = files.flatMap((f) =>
      (f.text.match(TAILWIND_PALETTE) ?? []).map((m) => `${f.path}: ${m}`),
    );
    expect(offenders).toEqual([]);
  });
});
