import type { HTMLAttributes } from "react";

export interface ChipProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "accent" | "success" | "warning" | "error";
}

function Chip({ className = "", variant = "default", children, ...props }: ChipProps) {
  const variants = {
    default: "border-border text-muted",
    accent: "border-accent/30 text-accent bg-accent/10",
    success: "border-green-500/30 text-green-400 bg-green-500/10",
    warning: "border-amber-500/30 text-amber-400 bg-amber-500/10",
    error: "border-red-500/30 text-red-400 bg-red-500/10",
  };
  return (
    <span
      className={`inline-block border rounded-full px-2 py-1 text-xs ${variants[variant]} ${className}`}
      {...props}
    >
      {children}
    </span>
  );
}

export { Chip };
