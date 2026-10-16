"""Tests for geocoding and OSRM routing (no network: requests.get is faked)."""

from __future__ import annotations

from typing import Any

import pytest
import requests

from gasolineras_core.config import NOMINATIM_URL, PHOTON_URL, USER_AGENT
from gasolineras_core.http_utils import RateLimiter
from gasolineras_core.ingestion import geocoder

OSRM_OK = {
    "code": "Ok",
    "routes": [{"geometry": {"coordinates": [[-4.66, 40.65], [-4.40, 40.80], [-4.12, 40.95]]}}],
}


class FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        return self._payload


class FakeGet:
    """Records calls and answers with a function of (url, params)."""

    def __init__(self, handler) -> None:
        self.handler = handler
        self.calls: list[dict[str, Any]] = []

    def __call__(self, url: str, params=None, headers=None, timeout=None) -> FakeResponse:
        self.calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        result = self.handler(url, params)
        if isinstance(result, Exception):
            raise result
        return result


@pytest.fixture(autouse=True)
def isolated_geocoder(monkeypatch):
    """Fresh caches and no real sleeping between requests."""
    geocoder.clear_caches()
    no_wait = RateLimiter(0.0, 10.0, sleep=lambda _s: None)
    monkeypatch.setattr(geocoder, "_nominatim_limiter", no_wait)
    monkeypatch.setattr(geocoder, "_photon_limiter", no_wait)
    monkeypatch.setattr(geocoder, "_suggest_limiter", no_wait)
    yield
    geocoder.clear_caches()


def nominatim_found(lat: float = 40.6572, lon: float = -4.6627):
    return FakeResponse([{"lat": str(lat), "lon": str(lon)}])


class TestGeocodePlace:
    def test_uses_nominatim_with_identifiable_user_agent(self, monkeypatch):
        fake = FakeGet(lambda url, params: nominatim_found())
        monkeypatch.setattr(geocoder.requests, "get", fake)

        place = geocoder.geocode_place("Ávila")

        assert (place.lat, place.lon, place.source) == (40.6572, -4.6627, "nominatim")
        call = fake.calls[0]
        assert call["url"] == NOMINATIM_URL
        assert call["headers"]["User-Agent"] == USER_AGENT
        assert "Mozilla" not in call["headers"]["User-Agent"]
        assert call["params"]["q"] == "Ávila, España"
        assert call["params"]["countrycodes"] == "es"
        assert call["timeout"] is not None

    def test_caches_by_normalized_text(self, monkeypatch):
        fake = FakeGet(lambda url, params: nominatim_found())
        monkeypatch.setattr(geocoder.requests, "get", fake)

        geocoder.geocode_place("Ávila")
        geocoder.geocode_place("  ávila ")
        geocoder.geocode_place("ÁVILA")

        assert len(fake.calls) == 1

    def test_falls_back_to_photon_when_nominatim_is_rate_limited(self, monkeypatch):
        def handler(url, params):
            if url == NOMINATIM_URL:
                return FakeResponse({}, status_code=429)
            return FakeResponse({"features": [{"geometry": {"coordinates": [-4.02, 39.86]}}]})

        fake = FakeGet(handler)
        monkeypatch.setattr(geocoder.requests, "get", fake)

        place = geocoder.geocode_place("Toledo")

        assert (place.lat, place.lon, place.source) == (39.86, -4.02, "photon")
        assert fake.calls[1]["url"] == PHOTON_URL
        assert "bbox" in fake.calls[1]["params"]  # restricted to Spain

    def test_not_found_raises_place_not_found_without_trying_photon(self, monkeypatch):
        fake = FakeGet(lambda url, params: FakeResponse([]))
        monkeypatch.setattr(geocoder.requests, "get", fake)

        with pytest.raises(geocoder.PlaceNotFoundError, match="Xyzzy"):
            geocoder.geocode_place("Xyzzy")
        assert len(fake.calls) == 1

    def test_not_found_is_not_cached(self, monkeypatch):
        fake = FakeGet(lambda url, params: FakeResponse([]))
        monkeypatch.setattr(geocoder.requests, "get", fake)

        for _ in range(2):
            with pytest.raises(geocoder.PlaceNotFoundError):
                geocoder.geocode_place("Xyzzy")
        assert len(fake.calls) == 2

    def test_all_services_down_raises_routing_service_error(self, monkeypatch):
        fake = FakeGet(lambda url, params: requests.ConnectionError("sin red (test)"))
        monkeypatch.setattr(geocoder.requests, "get", fake)

        with pytest.raises(geocoder.RoutingServiceError):
            geocoder.geocode_place("Ávila")
        assert len(fake.calls) == 2

    def test_busy_rate_limiter_counts_as_service_unavailable(self, monkeypatch):
        busy = RateLimiter(1.0, 0.0, sleep=lambda _s: None)
        busy.wait()  # next slot is 1 s away, max wait is 0 s
        monkeypatch.setattr(geocoder, "_nominatim_limiter", busy)
        monkeypatch.setattr(geocoder, "_photon_limiter", busy)
        fake = FakeGet(lambda url, params: nominatim_found())
        monkeypatch.setattr(geocoder.requests, "get", fake)

        with pytest.raises(geocoder.RoutingServiceError):
            geocoder.geocode_place("Ávila")
        assert fake.calls == []

    def test_empty_place_is_rejected_without_network(self, monkeypatch):
        fake = FakeGet(lambda url, params: nominatim_found())
        monkeypatch.setattr(geocoder.requests, "get", fake)

        with pytest.raises(geocoder.PlaceNotFoundError):
            geocoder.geocode_place("   ")
        assert fake.calls == []


class TestFetchRoadRoute:
    def test_returns_track_and_caches_it(self, monkeypatch):
        fake = FakeGet(lambda url, params: FakeResponse(OSRM_OK))
        monkeypatch.setattr(geocoder.requests, "get", fake)

        track = geocoder.fetch_road_route((40.65, -4.66), (40.95, -4.12))
        again = geocoder.fetch_road_route((40.650001, -4.660001), (40.95, -4.12))

        assert list(track.coords)[0] == (-4.66, 40.65)
        assert again.equals(track)
        assert len(fake.calls) == 1
        assert fake.calls[0]["headers"]["User-Agent"] == USER_AGENT
        assert "-4.66,40.65;-4.12,40.95" in fake.calls[0]["url"]  # OSRM expects lon,lat

    def test_details_include_the_osrm_duration(self, monkeypatch):
        with_duration = {"code": "Ok", "routes": [{**OSRM_OK["routes"][0], "duration": 3720.5}]}
        monkeypatch.setattr(geocoder.requests, "get", FakeGet(lambda url, params: FakeResponse(with_duration)))

        route = geocoder.fetch_road_route_details((40.65, -4.66), (40.95, -4.12))

        assert route.duration_s == 3720.5
        assert len(route.track.coords) == 3

    def test_details_without_duration_say_so(self, monkeypatch):
        monkeypatch.setattr(geocoder.requests, "get", FakeGet(lambda url, params: FakeResponse(OSRM_OK)))

        assert geocoder.fetch_road_route_details((40.65, -4.66), (40.95, -4.12)).duration_s is None

    def test_osrm_no_route_raises_no_route_error(self, monkeypatch):
        fake = FakeGet(lambda url, params: FakeResponse({"code": "NoRoute"}, status_code=400))
        monkeypatch.setattr(geocoder.requests, "get", fake)

        with pytest.raises(geocoder.NoRouteError):
            geocoder.fetch_road_route((40.65, -4.66), (28.1, -15.4))
        assert len(fake.calls) == 1

    def test_tries_next_server_and_raises_service_error_if_all_fail(self, monkeypatch):
        fake = FakeGet(lambda url, params: FakeResponse({}, status_code=429))
        monkeypatch.setattr(geocoder.requests, "get", fake)

        with pytest.raises(geocoder.RoutingServiceError):
            geocoder.fetch_road_route((40.65, -4.66), (40.95, -4.12))
        assert len(fake.calls) == 3


class TestGetRouteFromText:
    def test_geocodes_both_places_and_routes_between_them(self, monkeypatch):
        def handler(url, params):
            if url == NOMINATIM_URL:
                return nominatim_found(40.65, -4.66) if "Ávila" in params["q"] else nominatim_found(40.95, -4.12)
            return FakeResponse(OSRM_OK)

        monkeypatch.setattr(geocoder.requests, "get", FakeGet(handler))

        track = geocoder.get_route_from_text("Ávila", "Segovia")

        assert len(track.coords) == 3

    def test_errors_are_still_route_text_errors_for_legacy_callers(self):
        for exc in (geocoder.PlaceNotFoundError, geocoder.NoRouteError, geocoder.RoutingServiceError):
            assert issubclass(exc, geocoder.RouteTextError)


def photon_place(name, kind, county=None, state=None, country="ES", lon=-3.7, lat=40.4):
    return {
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {"name": name, "osm_value": kind, "county": county, "state": state, "countrycode": country},
    }


PHOTON_VALEN = {
    "features": [
        photon_place("Valentine", "village", "Haute-Garonne", "Occitanie", country="FR"),
        photon_place("Valencia de Don Juan", "village", "León", "Castilla y León"),
        photon_place("València / Valencia", "province", None, "Comunitat Valenciana"),
        photon_place("València", "city", "Comarca de València", "Comunitat Valenciana", lon=-0.376, lat=39.47),
        photon_place("Valencia de Alcántara", "town", "Cáceres", "Extremadura"),
        photon_place("Valencia de Don Juan", "village", "León", "Castilla y León"),
    ]
}


class TestParsePhotonSuggestions:
    def test_keeps_spanish_places_most_important_first_without_repeats(self):
        suggestions = geocoder.parse_photon_suggestions(PHOTON_VALEN)

        assert [(s.name, s.kind) for s in suggestions] == [
            ("València", "city"),
            ("Valencia de Alcántara", "town"),
            ("Valencia de Don Juan", "village"),
        ]
        assert suggestions[0].context == "Comarca de València, Comunitat Valenciana"
        assert (suggestions[0].lat, suggestions[0].lon) == (39.47, -0.376)

    def test_context_skips_parts_equal_to_the_name(self):
        payload = {"features": [photon_place("Madrid", "city", None, "Comunidad de Madrid")]}

        assert geocoder.parse_photon_suggestions(payload)[0].context == "Comunidad de Madrid"

    def test_respects_the_limit_and_tolerates_malformed_features(self):
        payload = {"features": [{"properties": {}}, *[photon_place(f"Pueblo {i}", "village") for i in range(9)]]}

        assert len(geocoder.parse_photon_suggestions(payload, limit=4)) == 4
        assert geocoder.parse_photon_suggestions({"error": "x"}) == []


class TestSuggestPlaces:
    def test_asks_photon_for_places_in_spain_with_identifiable_user_agent(self, monkeypatch):
        fake = FakeGet(lambda url, params: FakeResponse(PHOTON_VALEN))
        monkeypatch.setattr(geocoder.requests, "get", fake)

        names = [s.name for s in geocoder.suggest_places("  Valen ")]

        assert names[0] == "València"
        call = fake.calls[0]
        assert call["url"] == PHOTON_URL
        assert call["params"]["q"] == "Valen"
        assert call["params"]["osm_tag"] == "place"
        assert call["headers"]["User-Agent"] == USER_AGENT
        assert call["timeout"] is not None

    def test_caches_by_normalized_text(self, monkeypatch):
        fake = FakeGet(lambda url, params: FakeResponse(PHOTON_VALEN))
        monkeypatch.setattr(geocoder.requests, "get", fake)

        geocoder.suggest_places("Valen")
        geocoder.suggest_places("VALEN ")

        assert len(fake.calls) == 1

    def test_too_short_queries_do_not_call_photon(self, monkeypatch):
        fake = FakeGet(lambda url, params: FakeResponse(PHOTON_VALEN))
        monkeypatch.setattr(geocoder.requests, "get", fake)

        assert geocoder.suggest_places(" v ") == []
        assert fake.calls == []

    def test_photon_down_raises_routing_service_error(self, monkeypatch):
        fake = FakeGet(lambda url, params: requests.ConnectionError("down"))
        monkeypatch.setattr(geocoder.requests, "get", fake)

        with pytest.raises(geocoder.RoutingServiceError):
            geocoder.suggest_places("Valen")
