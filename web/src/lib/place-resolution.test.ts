import { describe, expect, it } from "vitest";

import type { PlaceSuggestion } from "@/lib/api/queries";

import { resolvePlace } from "./place-resolution";

const place = (name: string, context = ""): PlaceSuggestion => ({
  name,
  context,
  lat: 40,
  lon: -3,
  kind: "city",
});

describe("resolvePlace", () => {
  it("keeps a place picked from the suggestions without asking again", async () => {
    const madrid = place("Madrid");
    const suggest = () => Promise.reject(new Error("should not be called"));

    expect(await resolvePlace({ text: "Madrid", place: madrid }, suggest)).toEqual({
      status: "found",
      place: madrid,
    });
  });

  it("accepts a typed name that matches a suggestion, ignoring accents, case and spaces", async () => {
    const avila = place("Ávila", "Castilla y León");

    expect(await resolvePlace({ text: "  avila " }, () => Promise.resolve([avila]))).toEqual({
      status: "found",
      place: avila,
    });
  });

  it("accepts any of the names of a bilingual place", async () => {
    const donostia = place("Donostia / San Sebastián");

    const result = await resolvePlace({ text: "San Sebastian" }, () => Promise.resolve([donostia]));

    expect(result).toEqual({ status: "found", place: donostia });
  });

  it("offers up to three alternatives for a misspelt place", async () => {
    const options = [place("Madrid"), place("Madridejos"), place("Madrigal"), place("Madroñera")];

    const result = await resolvePlace({ text: "Mdrid" }, () => Promise.resolve(options));

    expect(result).toEqual({ status: "unknown", alternatives: options.slice(0, 3) });
  });

  it("does not block the search when suggestions are unavailable", async () => {
    expect(await resolvePlace({ text: "Madrid" }, () => Promise.reject(new Error("503")))).toEqual({
      status: "unchecked",
    });
  });
});
