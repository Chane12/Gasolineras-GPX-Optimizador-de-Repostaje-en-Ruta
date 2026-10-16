import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SEEN_FLUSH_MS, useSeenKeys } from "./use-seen-keys";

/** IntersectionObserver de mentira: el test decide qué elementos "aparecen". */
class FakeObserver {
  static instances: FakeObserver[] = [];
  observed = new Set<Element>();
  constructor(private readonly callback: IntersectionObserverCallback) {
    FakeObserver.instances.push(this);
  }
  observe(element: Element) {
    this.observed.add(element);
  }
  unobserve(element: Element) {
    this.observed.delete(element);
  }
  disconnect() {
    this.observed.clear();
  }
  show(elements: Element[]) {
    this.callback(
      elements.map((target) => ({ target, isIntersecting: true }) as IntersectionObserverEntry),
      this as unknown as IntersectionObserver,
    );
  }
}

function List({
  keys,
  enabled,
  onSeen,
}: {
  keys: string[];
  enabled: boolean;
  onSeen: (s: ReadonlySet<string>) => void;
}) {
  const { seen, observe } = useSeenKeys(enabled);
  onSeen(seen);
  return (
    <ul>
      {keys.map((k) => (
        <li key={k} ref={enabled ? observe(k) : undefined} data-key={k}>
          {k}
        </li>
      ))}
    </ul>
  );
}

describe("useSeenKeys", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeObserver.instances = [];
    vi.stubGlobal("IntersectionObserver", FakeObserver);
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("collects the rows that appear, in one batch, and never forgets them", () => {
    let seen: ReadonlySet<string> = new Set();
    const { container } = render(<List keys={["a", "b", "c"]} enabled onSeen={(s) => (seen = s)} />);
    const observer = FakeObserver.instances.at(-1);
    const row = (k: string) => container.querySelector(`[data-key="${k}"]`) as Element;
    expect(observer?.observed.size).toBe(3);

    act(() => observer?.show([row("a")]));
    act(() => observer?.show([row("b")]));
    expect(seen.size).toBe(0);
    act(() => vi.advanceTimersByTime(SEEN_FLUSH_MS));
    expect([...seen]).toEqual(["a", "b"]);
    // Ya vistas: se dejan de observar.
    expect(observer?.observed.has(row("a"))).toBe(false);
    expect(observer?.observed.has(row("c"))).toBe(true);
  });

  it("observes nothing while disabled", () => {
    render(<List keys={["a"]} enabled={false} onSeen={() => {}} />);
    expect(FakeObserver.instances).toHaveLength(0);
  });
});
