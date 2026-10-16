"use client";

import { useEffect, useState } from "react";

/**
 * Estado que se recuerda en el dispositivo (localStorage), para ajustes personales sin cuenta. Sin
 * almacenamiento (navegación privada, servidor) funciona igual, solo que no se recuerda.
 */
export function useStoredState<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const saved = localStorage.getItem(key);
      return saved === null ? initial : (JSON.parse(saved) as T);
    } catch {
      return initial;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // Sin almacenamiento: dura lo que la página.
    }
  }, [key, value]);
  return [value, setValue] as const;
}
