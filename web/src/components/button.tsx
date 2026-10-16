import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "quiet";
type Size = "lg" | "md";

interface ButtonStyle {
  variant?: Variant;
  size?: Size;
  block?: boolean;
}

const base =
  "inline-flex items-center justify-center gap-2 font-sans font-bold whitespace-nowrap transition-colors " +
  "disabled:cursor-not-allowed disabled:opacity-50";

const variants: Record<Variant, string> = {
  primary: "bg-accent text-on-accent hover:bg-accent-strong",
  secondary: "border-[1.5px] border-ink text-ink bg-transparent hover:bg-rule-soft",
  quiet: "text-accent bg-transparent hover:text-accent-strong px-0.5",
};

const sizes: Record<Size, string> = {
  lg: "h-[54px] px-5 text-[17px] rounded-button",
  md: "h-11 px-4 text-[15px] rounded-field",
};

export function buttonClasses({ variant = "primary", size = "md", block = false }: ButtonStyle = {}): string {
  const sizing = variant === "quiet" ? "h-11 text-[15px]" : sizes[size];
  return [base, variants[variant], sizing, block ? "w-full" : ""].filter(Boolean).join(" ");
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & ButtonStyle;

export function Button({ variant, size, block, className, type = "button", ...props }: ButtonProps) {
  return (
    <button
      type={type}
      className={[buttonClasses({ variant, size, block }), className].join(" ")}
      {...props}
    />
  );
}

type ButtonLinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & ButtonStyle & { href: string };

/** Enlace con aspecto de botón (navegar, abrir Google Maps…): sigue siendo un <a> real. */
export function ButtonLink({ variant, size, block, className, ...props }: ButtonLinkProps) {
  return (
    <a
      className={[buttonClasses({ variant, size, block }), "no-underline", className].join(" ")}
      {...props}
    />
  );
}

type IconButtonTone = "outline" | "filled" | "plain";

interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  /** Obligatorio: es lo que oye un lector de pantalla. */
  label: string;
  icon: ReactNode;
  tone?: IconButtonTone;
}

const iconTones: Record<IconButtonTone, string> = {
  outline: "border-[1.5px] border-accent text-accent bg-surface hover:bg-rule-soft",
  filled: "bg-accent text-on-accent hover:bg-accent-strong",
  plain: "text-muted bg-transparent hover:text-ink hover:bg-rule-soft",
};

/** Botón cuadrado de 44 px (objetivo táctil mínimo) con solo un icono. */
export function IconButton({
  label,
  icon,
  tone = "outline",
  className,
  type = "button",
  ...props
}: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      className={[
        "inline-flex size-11 shrink-0 items-center justify-center rounded-field transition-colors",
        iconTones[tone],
        className,
      ].join(" ")}
      {...props}
    >
      {icon}
    </button>
  );
}
