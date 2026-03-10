import { forwardRef, type ButtonHTMLAttributes } from "react";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "primary" | "ghost";
  size?: "sm" | "md" | "lg";
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className = "", variant = "default", size = "md", ...props }, ref) => {
    const base =
      "inline-flex items-center justify-center font-medium transition-colors active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2";

    const variants = {
      default: "border border-border bg-card text-foreground hover:bg-muted/10",
      primary: "border border-accent bg-accent text-black hover:bg-accent/90",
      ghost: "text-muted hover:text-foreground hover:bg-muted/10",
    };

    const sizes = {
      sm: "px-3 py-1.5 text-xs rounded-md",
      md: "px-4 py-2 text-sm rounded-lg",
      lg: "px-6 py-3 text-base rounded-lg",
    };

    return (
      <button
        ref={ref}
        className={`${base} ${variants[variant]} ${sizes[size]} ${className}`}
        {...props}
      />
    );
  },
);

Button.displayName = "Button";
export { Button };
