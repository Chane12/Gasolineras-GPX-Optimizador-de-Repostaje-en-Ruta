import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fakeApi, jsonResponse } from "@/test-utils";

import { useDetours } from "./detours";

const route = {
  key: "madrid-valencia",
  track: {
    coordinates: [
      [-3.7, 40.4],
      [-0.37, 39.47],
    ],
  },
};
const stations = [
  { id: "1", lat: 40, lon: -3 },
  { id: "2", lat: 39.8, lon: -2 },
];

/** API de desvíos simulada: `answer` decide el desvío de cada id en cada llamada (null = sin calcular). */
function detoursApi(answer: (id: string, call: number) => number | null) {
  const calls: string[][] = [];
  const client = fakeApi(async (request) => {
    const body = (await request.json()) as { stations: { id: string; lat: number; lon: number }[] };
    const call = calls.push(body.stations.map((s) => s.id));
    const detours = body.stations.map((s) => {
      const km = answer(s.id, call);
      return { id: s.id, lat: s.lat, lon: s.lon, detour_km: km, detour_min: km === null ? null : km * 2 };
    });
    return jsonResponse({ detours, complete: detours.every((d) => d.detour_km !== null) });
  });
  return { client, calls };
}

async function flush(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("useDetours", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("fetches the detours in the background", async () => {
    const { client, calls } = detoursApi(() => 1.2);
    const { result } = renderHook(() => useDetours(route, stations, client));

    expect(result.current.size).toBe(0);
    await flush();

    expect(calls).toEqual([["1", "2"]]);
    expect(result.current.get("1")).toEqual({ km: 1.2, minutes: 2.4, attempts: 1 });
  });

  it("asks again only for the missing ones, after a pause", async () => {
    const { client, calls } = detoursApi((id, call) => (id === "2" && call === 1 ? null : 0.8));
    const { result } = renderHook(() => useDetours(route, stations, client));

    await flush();
    expect(result.current.get("2")?.km).toBeNull();
    await flush(3_000);
    expect(calls).toHaveLength(1);

    await flush(1_500);
    expect(calls).toEqual([["1", "2"], ["2"]]);
    expect(result.current.get("2")).toEqual({ km: 0.8, minutes: 1.6, attempts: 2 });
  });

  it("gives up after three attempts", async () => {
    const { client, calls } = detoursApi(() => null);
    const { result } = renderHook(() => useDetours(route, stations, client));

    await flush();
    await flush(4_000);
    await flush(12_000);
    await flush(60_000);

    expect(calls).toHaveLength(3);
    expect(result.current.get("1")).toEqual({ km: null, minutes: null, attempts: 3 });
  });

  it("does nothing without a route", async () => {
    const { client, calls } = detoursApi(() => 1);
    renderHook(() => useDetours(null, stations, client));

    await flush(20_000);
    expect(calls).toEqual([]);
  });
});
