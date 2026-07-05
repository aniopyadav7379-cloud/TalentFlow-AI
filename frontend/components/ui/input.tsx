import { forwardRef } from "react";

import { cn } from "@/lib/utils";

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(({ className, error, ...props }, ref) => {
  return (
    <div className="w-full">
      <input
        ref={ref}
        className={cn(
          "h-10 w-full rounded-lg border bg-surface px-3 text-sm text-foreground placeholder:text-muted",
          "transition-colors duration-150 focus:outline-none",
          error ? "border-error focus:border-error" : "border-border focus:border-primary",
          className
        )}
        aria-invalid={!!error}
        {...props}
      />
      {error && <p className="mt-1 text-xs text-error">{error}</p>}
    </div>
  );
});
Input.displayName = "Input";

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(({ className, error, ...props }, ref) => {
  return (
    <div className="w-full">
      <textarea
        ref={ref}
        className={cn(
          "w-full rounded-lg border bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted",
          "transition-colors duration-150 focus:outline-none min-h-[100px] resize-y",
          error ? "border-error focus:border-error" : "border-border focus:border-primary",
          className
        )}
        aria-invalid={!!error}
        {...props}
      />
      {error && <p className="mt-1 text-xs text-error">{error}</p>}
    </div>
  );
});
Textarea.displayName = "Textarea";

export function Label({ className, children, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label className={cn("mb-1.5 block text-sm font-medium text-muted-foreground", className)} {...props}>
      {children}
    </label>
  );
}
