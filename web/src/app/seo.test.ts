import { describe, expect, it } from "vitest";

import { robotsFor } from "./robots";
import sitemap from "./sitemap";

describe("SEO", () => {
  it("keeps search engines out until launch", () => {
    expect(robotsFor(false)).toEqual({ rules: { userAgent: "*", disallow: "/" } });
  });

  it("opens the site at launch, except the design catalogue and the search results", () => {
    const robots = robotsFor(true);
    expect(robots.rules).toEqual({ userAgent: "*", allow: "/", disallow: ["/diseno", "/ruta"] });
    expect(robots.sitemap).toMatch(/\/sitemap\.xml$/);
  });

  it("lists only the fixed pages in the sitemap", () => {
    expect(sitemap().map((e) => new URL(e.url).pathname)).toEqual(["/", "/fuentes", "/privacidad"]);
  });
});
