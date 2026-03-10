import { forwardRef, type InputHTMLAttributes, type TextareaHTMLAttributes } from "react";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className = "", label, error, id, ...props }, ref) => (
    <div>
      {label && (
        <label htmlFor={id} className="text-sm text-muted mb-1.5 block">
          {label}
        </label>
      )}
      <input
        ref={ref}
        id={id}
        className={`w-full bg-background border border-border rounded-lg px-4 py-2 text-sm text-foreground placeholder:text-muted/60 focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent disabled:opacity-50 ${error ? "border-red-500 focus:ring-red-500" : ""} ${className}`}
        {...props}
      />
      {error && <p className="text-xs text-red-400 mt-1">{error}</p>}
    </div>
  ),
);
Input.displayName = "Input";

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
}

const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className = "", label, error, id, ...props }, ref) => (
    <div>
      {label && (
        <label htmlFor={id} className="text-sm text-muted mb-1.5 block">
          {label}
        </label>
      )}
      <textarea
        ref={ref}
        id={id}
        className={`w-full bg-background border border-border rounded-lg px-4 py-2 text-sm text-foreground placeholder:text-muted/60 focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent disabled:opacity-50 resize-none json-area ${error ? "border-red-500 focus:ring-red-500" : ""} ${className}`}
        {...props}
      />
      {error && <p className="text-xs text-red-400 mt-1">{error}</p>}
    </div>
  ),
);
Textarea.displayName = "Textarea";

export { Input, Textarea };
