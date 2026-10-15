"""Check that the production Streamlit app loads without errors (uses network and the system Chrome).

Run from the repo root after merging anything that reaches production:
    uvx --from playwright python scripts/check_prod.py

Exit code 0 if the app renders its sidebar and no exception; 1 otherwise. Saves a screenshot to
$CHECK_PROD_SCREENSHOT (default: prod.png in the system temp dir).
"""

import os
import sys
import tempfile

from playwright.sync_api import Frame, sync_playwright

PROD_URL = "https://gasolineras-gpx-optimizador-de-repostaje-en-ruta.streamlit.app/"
APP_FRAME_MARKER = "/~/+/"  # Streamlit Community Cloud serves the app inside this iframe
LOAD_TIMEOUT_S = 120


def find_app_frame(frames: list[Frame]) -> Frame | None:
    return next((f for f in frames if APP_FRAME_MARKER in f.url), None)


def main() -> int:
    screenshot = os.environ.get("CHECK_PROD_SCREENSHOT", os.path.join(tempfile.gettempdir(), "prod.png"))
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.goto(PROD_URL, timeout=LOAD_TIMEOUT_S * 1000)

        frame = None
        rendered = False
        # A sleeping app takes a while to wake up, so poll instead of a single wait.
        for _ in range(LOAD_TIMEOUT_S):
            frame = find_app_frame(page.frames)
            if frame and frame.locator('[data-testid="stSidebar"], [data-testid="stException"]').count():
                rendered = True
                break
            page.wait_for_timeout(1000)
        page.wait_for_timeout(3000)
        page.screenshot(path=screenshot)

        if not frame or not rendered:
            print(f"✗ La app no ha cargado en {LOAD_TIMEOUT_S} s. Captura: {screenshot}")
            print(" ".join(page.inner_text("body").split())[:500])
            return 1

        exceptions = frame.locator('[data-testid="stException"]').all_inner_texts()
        text = " ".join(frame.inner_text("body").split())
        browser.close()

    if exceptions:
        print("✗ La app muestra errores:")
        for exc in exceptions[:3]:
            print("  ", exc[:500])
        return 1
    freshness = next((s for s in text.split("📡")[1:2]), "").split(".")[0]
    print(f"✔ Producción OK.{(' 📡' + freshness) if freshness else ''} Captura: {screenshot}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
