"""
Smoke test de la app Streamlit legacy: arranca, ejecuta la ruta de demo y falla si hay excepciones.
Usa la red (MITECO). Ejecutar desde la raíz: uv run python scripts/smoke_legacy.py
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "legacy" / "streamlit"))  # `streamlit run` lo hace solo; AppTest no

from streamlit.testing.v1 import AppTest  # noqa: E402

at = AppTest.from_file(str(ROOT / "legacy" / "streamlit" / "app.py"), default_timeout=180)
at.run()
assert not at.exception, f"Excepción al arrancar: {[e.value for e in at.exception]}"
# El shim de app.py debe poner core/src en el PYTHONPATH: así Streamlit vigila y recarga el core tras un despliegue.
assert str(ROOT / "core" / "src") in os.environ.get("PYTHONPATH", "").split(os.pathsep), (
    "core/src no está en PYTHONPATH"
)

at.session_state["demo_mode"] = True
at.run()
assert not at.exception, f"Excepción en la demo: {[e.value for e in at.exception]}"
assert not at.error, f"Errores en la UI: {[e.value for e in at.error]}"

results = at.session_state["pipeline_results"]
assert len(results["gdf_top"]) > 0, "La demo no devolvió gasolineras"
print(f"✔ Demo OK: {len(results['gdf_top'])} gasolineras sugeridas, {len(results['gdf_within'])} en el corredor")
