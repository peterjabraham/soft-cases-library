import type { HTMLAttributes } from "react";

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  padding?: "sm" | "md" | "lg";
}

function Card({ className = "", padding = "md", children, ...props }: CardProps) {
  const p = { sm: "p-3", md: "p-4", lg: "p-6" };
  return (
    <div
      className={`bg-card border border-border rounded-lg ${p[padding]} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

function CardHeader({ className = "", children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`mb-3 ${className}`} {...props}>{children}</div>;
}

function CardTitle({ className = "", children, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3 className={`text-lg font-black text-foreground ${className}`} {...props}>
      {children}
    </h3>
  );
}

function CardDescription({ className = "", children, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={`text-sm text-muted ${className}`} {...props}>{children}</p>;
}

export { Card, CardHeader, CardTitle, CardDescription };
