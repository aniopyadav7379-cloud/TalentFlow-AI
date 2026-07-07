"use client";

import { motion } from "framer-motion";

/**
 * Purely decorative, absolutely-positioned glow blobs behind the dashboard
 * content. Pointer-events are disabled so it never blocks clicks, and it
 * respects prefers-reduced-motion via the global rule in globals.css.
 * No data, no props needed — safe to drop into any layout.
 */
export function AnimatedBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <motion.div
        className="absolute -left-32 -top-32 h-[420px] w-[420px] rounded-full bg-primary/25 blur-[120px]"
        animate={{
          x: [0, 60, -20, 0],
          y: [0, 40, 80, 0],
          scale: [1, 1.15, 0.95, 1],
        }}
        transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute right-[-10%] top-1/4 h-[380px] w-[380px] rounded-full bg-accent/20 blur-[130px]"
        animate={{
          x: [0, -50, 30, 0],
          y: [0, 60, -40, 0],
          scale: [1, 0.9, 1.2, 1],
        }}
        transition={{ duration: 26, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute bottom-[-15%] left-1/3 h-[460px] w-[460px] rounded-full bg-primary/15 blur-[140px]"
        animate={{
          x: [0, 40, -60, 0],
          y: [0, -30, 20, 0],
          scale: [1, 1.1, 0.95, 1],
        }}
        transition={{ duration: 30, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
}