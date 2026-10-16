import { ServerWarmupNotice } from "@/components/server-warmup-notice";

export default function Home() {
  return (
    <main className="mx-auto max-w-xl px-4 py-16">
      <h1 className="text-3xl font-bold">Gasolineras en Ruta</h1>
      <p className="mt-3">La web nueva está en construcción.</p>
      <div className="mt-6">
        <ServerWarmupNotice />
      </div>
    </main>
  );
}
