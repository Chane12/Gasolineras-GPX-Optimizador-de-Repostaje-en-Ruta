import { describe, expect, it } from "vitest";

import { robotsHeaders } from "../next.config";

describe("robotsHeaders", () => {
  it("keeps search engines out until the site is declared indexable", () => {
    expect(robotsHeaders(false)).toEqual([
      { source: "/:path*", headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }] },
    ]);
    expect(robotsHeaders(true)).toEqual([]);
  });
});
