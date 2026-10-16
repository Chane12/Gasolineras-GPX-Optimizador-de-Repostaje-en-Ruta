"""Capturas de la web en móvil (390 × 844) y ordenador (1440 × 900), en claro y oscuro.

Es el "listón de calidad" de docs/web/plan.md: cada PR visual se revisa con estas capturas contra las
maquetas de docs/web/maquetas/flujo/. Usa el Chrome del sistema (como check_prod.py).

    uvx --from playwright python scripts/screenshots.py                       # web local (pnpm dev)
    uvx --from playwright python scripts/screenshots.py --base-url https://gasolineras-web.vercel.app
    uvx --from playwright python scripts/screenshots.py --out /tmp/capturas --only ruta

La web local debe hablar con una API que responda (p. ej. NEXT_PUBLIC_API_URL con la de Render).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

SIZES = {"movil": (390, 844), "ordenador": (1440, 900)}
SCHEMES = ("light", "dark")
# Pantallas: nombre → (ruta, texto que indica que ya ha cargado).
PAGES = {
    "inicio": ("/", "Organiza tu ruta"),
    "ruta": ("/ruta?demo=true", "Elige tus paradas"),
    # La hoja de ruta se abre desde la ruta de ejemplo, eligiendo antes dos paradas (ver open_roadbook).
    "hoja": ("/ruta?demo=true", "Repostar"),
}


def open_roadbook(page) -> None:
    """Desde la ruta de ejemplo: añade dos paradas y abre la hoja de ruta."""
    page.get_by_text("Elige tus paradas").first.wait_for(timeout=LOAD_TIMEOUT_MS)
    page.get_by_text("MÁS BARATA").first.wait_for(timeout=LOAD_TIMEOUT_MS)
    for _ in range(2):
        page.get_by_role("button", name="Añadir").first.click()
        page.wait_for_timeout(300)
    page.get_by_role("link", name="Hoja de ruta").click()


LOAD_TIMEOUT_MS = 120_000  # la API gratuita puede tardar en despertar
SETTLE_MS = 5_000  # teselas del mapa


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://localhost:3000")
    parser.add_argument("--out", default="capturas", type=Path)
    parser.add_argument("--only", choices=sorted(PAGES), help="solo esta pantalla")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    pages = {args.only: PAGES[args.only]} if args.only else PAGES
    failures = 0
    with sync_playwright() as p:
        # SwiftShader: WebGL por software, para que el mapa (MapLibre) se pinte también sin GPU.
        browser = p.chromium.launch(channel="chrome", args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        for size_name, (width, height) in SIZES.items():
            for scheme in SCHEMES:
                context = browser.new_context(viewport={"width": width, "height": height}, color_scheme=scheme)
                page = context.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
                for name, (path, ready_text) in pages.items():
                    target = args.out / f"{name}-{size_name}-{scheme}.png"
                    try:
                        page.goto(args.base_url + path, wait_until="domcontentloaded")
                        if name == "hoja":
                            open_roadbook(page)
                        page.get_by_text(ready_text).first.wait_for(timeout=LOAD_TIMEOUT_MS)
                        page.wait_for_timeout(SETTLE_MS)
                        page.screenshot(path=target)
                        print(f"✔ {target}")
                    except Exception as exc:  # una pantalla rota no impide capturar las demás
                        failures += 1
                        print(f"✗ {name} ({size_name}, {scheme}): {exc}", file=sys.stderr)
                for error in errors:
                    failures += 1
                    print(f"✗ Error de JavaScript ({size_name}, {scheme}): {error}", file=sys.stderr)
                context.close()
        browser.close()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
