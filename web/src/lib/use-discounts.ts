"use client";

import { useEffect, useState } from "react";

import { type Discount, isValidDiscount } from "@/lib/discounts";

const STORAGE_KEY = "gasolineras:descuentos";

function load(): Discount[] {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]") as unknown;
    return Array.isArray(saved) ? (saved as Discount[]) : [];
  } catch {
    return [];
  }
}

/** Mis descuentos (punto 10c), guardados en el dispositivo. `active` = cuántos son válidos. */
export function useDiscounts() {
  const [discounts, setDiscounts] = useState<Discount[]>(load);
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(discounts));
    } catch {
      // Sin almacenamiento: duran lo que la página.
    }
  }, [discounts]);
  return { discounts, setDiscounts, active: discounts.filter(isValidDiscount).length };
}
