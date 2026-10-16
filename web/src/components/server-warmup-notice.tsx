"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/button";
import { WarningIcon } from "@/components/icons";
import { api, type ApiClient } from "@/lib/api/client";
import { useHealth } from "@/lib/api/queries";

/**
 * Despierta la API en cuanto se abre la web y avisa si tarda. El alojamiento gratuito (Render) duerme
 * la API tras un rato sin uso y tarda ~50 s en despertar: mejor explicarlo que mostrar un error.
 */
export function ServerWarmupNotice({
  client = api,
  slowAfterMs = 2500,
}: {
  client?: ApiClient;
  slowAfterMs?: number;
}) {
  const health = useHealth(client);
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    if (!health.isPending) return;
    const timer = setTimeout(() => setSlow(true), slowAfterMs);
    return () => clearTimeout(timer);
  }, [health.isPending, slowAfterMs]);

  if (health.isError) {
    return (
      <div
        role="alert"
        className="flex items-center gap-3 rounded-card border-[1.5px] border-ink p-3 text-[15px]"
      >
        <WarningIcon size={20} className="shrink-0 text-warn" />
        <span className="flex-1">{health.error.message}</span>
        <Button variant="secondary" onClick={() => void health.refetch()}>
          Reintentar
        </Button>
      </div>
    );
  }

  if (health.isPending && slow) {
    return (
      <div role="status" className="flex items-center gap-3 rounded-card border border-rule p-3 text-[15px]">
        <span aria-hidden="true" className="size-2.5 shrink-0 animate-pulse rounded-full bg-accent" />
        <span>
          <b>Despertando el servidor…</b>{" "}
          <span className="text-muted">
            Tras un rato sin uso tarda hasta un minuto. Puedes ir rellenando la ruta.
          </span>
        </span>
      </div>
    );
  }

  return null;
}
