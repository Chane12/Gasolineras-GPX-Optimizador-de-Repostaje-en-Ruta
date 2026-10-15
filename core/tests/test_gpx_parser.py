"""Tests for parsing GPX content from memory (uploads)."""

from pathlib import Path

import pytest

from gasolineras_core.ingestion.gpx_parser import load_gpx_track, parse_gpx_track

ROUTE_ONLY_GPX = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">
  <rte><rtept lat="40.65" lon="-4.66"/><rtept lat="40.95" lon="-4.12"/></rte>
</gpx>"""


def test_bytes_give_the_same_track_as_the_file(sample_gpx_path: Path):
    from_bytes = parse_gpx_track(sample_gpx_path.read_bytes())
    assert from_bytes.equals(load_gpx_track(sample_gpx_path))


def test_accepts_utf8_bom(sample_gpx_path: Path):
    track = parse_gpx_track(b"\xef\xbb\xbf" + sample_gpx_path.read_bytes())
    assert len(track.coords) == 20


def test_accepts_latin1_encoded_files():
    data = ROUTE_ONLY_GPX.replace('creator="test"', 'creator="Ávila"').replace("UTF-8", "ISO-8859-1")
    track = parse_gpx_track(data.encode("latin-1"))
    assert len(track.coords) == 2


def test_falls_back_to_route_points_when_there_is_no_track():
    track = parse_gpx_track(ROUTE_ONLY_GPX)
    assert list(track.coords) == [(-4.66, 40.65), (-4.12, 40.95)]


def test_invalid_xml_raises_value_error_with_file_name():
    with pytest.raises(ValueError, match="mi_ruta.gpx"):
        parse_gpx_track(b"esto no es un gpx", name="mi_ruta.gpx")


def test_fewer_than_two_points_raises_value_error():
    one_point = ROUTE_ONLY_GPX.replace('<rtept lat="40.95" lon="-4.12"/>', "")
    with pytest.raises(ValueError, match="al menos 2 puntos"):
        parse_gpx_track(one_point)
