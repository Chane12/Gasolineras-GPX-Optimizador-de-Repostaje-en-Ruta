"""
main.py
=======
CLI entrypoint — pure orchestrator. No business logic.

Usage:
    uv run python main.py
    uv run python main.py --gpx ruta.gpx --fuel "Precio Gasolina 95 E5" --buffer 3000 --top 10
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd

from src.config import CRS_UTM30N, CRS_WGS84, PROJECT_ROOT
from src.ingestion.gpx_parser import load_gpx_track, simplify_track, validate_gpx_track
from src.ingestion.miteco import fetch_gasolineras
from src.optimizer.cheapest import filter_cheapest_stations
from src.spatial.engine import build_route_buffer, build_stations_geodataframe, spatial_join_within_buffer
from src.visualization.folium_map import generate_map


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Optimizador de Gasolineras en Ruta — España",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Ejemplos:
  uv run python main.py --gpx sierra_gredos.gpx
  uv run python main.py --gpx ruta.gpx --fuel "Precio Gasolina 95 E5" --top 10
  uv run python main.py --gpx ruta.gpx --buffer 3000 --segment-km 50
        """,
    )
    parser.add_argument("--gpx", type=str, default="sierra_gredos.gpx", help="Ruta al archivo .gpx")
    parser.add_argument("--fuel", type=str, default="Precio Gasoleo A", help="Columna de precio de fuel")
    parser.add_argument("--buffer", type=float, default=5000.0, help="Radio del buffer en metros")
    parser.add_argument("--top", type=int, default=5, help="Número de gasolineras más baratas")
    parser.add_argument("--tolerance", type=float, default=0.0005, help="Tolerancia RDP en grados")
    parser.add_argument("--segment-km", type=float, default=0.0, help="Intervalo tramos (km), 0=desactivado")
    parser.add_argument("--output-html", type=str, default=None, help="Ruta de salida del mapa HTML")

    args = parser.parse_args()

    print("=" * 60)
    print(" OPTIMIZADOR DE GASOLINERAS EN RUTA — España")
    print("=" * 60)

    # --- Resolve GPX path relative to project root ---
    gpx_path = Path(args.gpx)
    if not gpx_path.is_absolute():
        gpx_path = PROJECT_ROOT / gpx_path

    if not gpx_path.exists():
        print(f"\n[ERROR] No se encontró '{gpx_path}'.")
        return

    # 1. Ingesta MITECO
    df_gasolineras = fetch_gasolineras()

    # 2. Cargar y procesar GPX
    track_original = load_gpx_track(gpx_path)
    validate_gpx_track(track_original)

    # 3. Simplificación RDP
    track_simplified = simplify_track(track_original, tolerance_deg=args.tolerance)

    # 4. Buffer + Spatial Join
    gdf_buffer = build_route_buffer(track_simplified, buffer_meters=args.buffer)
    gdf_stations_utm = build_stations_geodataframe(df_gasolineras)
    gdf_within = spatial_join_within_buffer(gdf_stations_utm, gdf_buffer)

    # Track en UTM
    gdf_track_utm = gpd.GeoDataFrame(geometry=[track_simplified], crs=CRS_WGS84).to_crs(CRS_UTM30N)
    track_utm = gdf_track_utm.geometry.iloc[0]

    # 5. Filtrado Top-N
    gdf_top = filter_cheapest_stations(
        gdf_within,
        fuel_column=args.fuel,
        top_n=args.top,
        track_utm=track_utm,
        segment_km=args.segment_km,
    )

    # 6. Mapa
    if not gdf_top.empty:
        generate_map(
            track_original=track_original,
            gdf_top_stations=gdf_top,
            fuel_column=args.fuel,
            output_path=args.output_html,
            gdf_all_stations=gdf_within,
        )
    else:
        print("[WARN] Sin gasolineras válidas para generar el mapa.")

    print("\n" + "=" * 60)
    print(" PIPELINE COMPLETADO")
    print("=" * 60)
    print(f"\n  - Combustible: {args.fuel}")
    print(f"  - Gasolineras encontradas en zona: {len(gdf_within)}")
    print(f"  - Top {args.top} mostradas.")


if __name__ == "__main__":
    main()
