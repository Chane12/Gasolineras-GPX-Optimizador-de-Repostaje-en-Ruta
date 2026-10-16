import type { ReactNode } from "react";

import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";

/** Plantilla de las páginas de información (fuentes, privacidad): texto legible, filetes y nada más. */
export function LegalPage({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-dvh flex-col">
      <SiteHeader />
      <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-8 lg:py-12">
        <p className="m-0 font-mono text-xs font-semibold tracking-[0.08em] text-muted">{eyebrow}</p>
        <h1 className="m-0 mt-2 text-[34px] leading-tight font-bold tracking-[-0.02em]">{title}</h1>
        <div className="mt-6 flex flex-col gap-6 text-[16px] leading-relaxed [&_h2]:m-0 [&_h2]:border-t-2 [&_h2]:border-ink [&_h2]:pt-3 [&_h2]:text-xl [&_h2]:font-bold [&_p]:m-0 [&_ul]:m-0 [&_ul]:flex [&_ul]:flex-col [&_ul]:gap-2 [&_ul]:pl-5 [&_a]:underline [&_a]:underline-offset-2">
          {children}
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
