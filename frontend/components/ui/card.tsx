"use client";

import { motion, type HTMLMotionProps } from "framer-motion";
import { forwardRef } from "react";

import { cn } from "@/lib/utils";

interface CardProps extends Omit<HTMLMotionProps<"div">, "ref" | "children"> {
  interactive?: boolean;
  children?: React.ReactNode;
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, interactive = false, children, ...props }, ref) => {
    return (
      <motion.div
        ref={ref}
        whileHover={interactive ? { y: -4 } : undefined}
        transition={{ duration: 0.2, ease: "easeOut" }}
        className={cn(
          "rounded-[20px] border border-border bg-card p-5",
          interactive &&
            "cursor-pointer transition-shadow duration-200 hover:border-primary/50 hover:shadow-[0_8px_30px_-8px_rgba(79,70,229,0.35)]",
          className
        )}
        {...props}
      >
        {children}
      </motion.div>
    );
  }
);
Card.displayName = "Card";

export function CardHeader({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("mb-4 flex items-center justify-between", className)}>{children}</div>;
}

export function CardTitle({ className, children }: { className?: string; children: React.ReactNode }) {
  return <h3 className={cn("text-base font-semibold text-foreground", className)}>{children}</h3>;
}
