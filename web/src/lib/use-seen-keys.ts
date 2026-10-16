"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/** Cada cuánto se juntan las filas vistas (al bajar deprisa, una sola tanda en vez de una por fila). */
export const SEEN_FLUSH_MS = 500;

type RefCallback = (element: HTMLElement | null) => void;

/**
 * Claves de las filas de una lista que ya han aparecido en pantalla. Cada fila se registra con
 * `observe(key)` como `ref`. Solo crece: lo visto una vez cuenta como visto. Se usa para pedir los desvíos
 * de "Ver todas" según se baja, sin pedir cientos de golpe. Sin IntersectionObserver, lo registrado cuenta
 * como visto.
 */
export function useSeenKeys(enabled: boolean): {
  seen: ReadonlySet<string>;
  observe: (key: string) => RefCallback;
} {
  const [seen, setSeen] = useState<ReadonlySet<string>>(() => new Set());
  const elements = useRef(new Map<Element, string>());
  const observer = useRef<IntersectionObserver | null>(null);
  const callbacks = useRef(new Map<string, RefCallback>());
  const batch = useRef<string[]>([]);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const flush = useCallback(() => {
    timer.current = null;
    const added = batch.current;
    batch.current = [];
    if (added.length === 0) return;
    setSeen((current) => (added.every((k) => current.has(k)) ? current : new Set([...current, ...added])));
  }, []);
  const mark = useCallback(
    (key: string) => {
      batch.current.push(key);
      timer.current ??= setTimeout(flush, SEEN_FLUSH_MS);
    },
    [flush],
  );

  useEffect(() => {
    if (!enabled) return;
    if (typeof IntersectionObserver === "undefined") {
      elements.current.forEach((key) => mark(key));
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const key = elements.current.get(entry.target);
          if (entry.isIntersecting && key) {
            mark(key);
            io.unobserve(entry.target);
          }
        }
      },
      // Un poco antes de que aparezcan, para que el desvío llegue a la vez que la fila.
      { rootMargin: "200px 0px" },
    );
    observer.current = io;
    elements.current.forEach((_, element) => io.observe(element));
    return () => {
      io.disconnect();
      observer.current = null;
      if (timer.current !== null) {
        clearTimeout(timer.current);
        flush();
      }
    };
  }, [enabled, mark, flush]);

  const observe = useCallback(
    (key: string): RefCallback => {
      let callback = callbacks.current.get(key);
      if (!callback) {
        let current: HTMLElement | null = null;
        callback = (element) => {
          if (current) {
            elements.current.delete(current);
            observer.current?.unobserve(current);
          }
          current = element;
          if (!element) return;
          elements.current.set(element, key);
          if (observer.current) observer.current.observe(element);
          else if (enabled && typeof IntersectionObserver === "undefined") mark(key);
        };
        callbacks.current.set(key, callback);
      }
      return callback;
    },
    [enabled, mark],
  );

  return { seen, observe };
}
