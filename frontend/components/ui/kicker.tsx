import type { HTMLAttributes } from "react";

function Kicker({ className = "", children, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={`text-xs tracking-wider uppercase text-muted mb-1.5 ${className}`} {...props}>
      {children}
    </p>
  );
}

export { Kicker };
