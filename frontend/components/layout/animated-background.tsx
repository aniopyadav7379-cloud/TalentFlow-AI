"use client";

import { motion } from "framer-motion";

/**
 * Lightning bolt path + its flicker timing. Each bolt fires irregularly
 * (fast double-flash, then a long dark pause) to feel like real electricity
 * rather than a smooth loop.
 */
const bolts = [
  {
    d: "M120 0 L95 160 L140 165 L60 380",
    top: "-5%",
    left: "8%",
    width: 200,
    height: 400,
    color: "var(--color-primary)",
    delay: 0,
  },
  {
    d: "M40 0 L70 140 L20 150 L90 340",
    top: "5%",
    right: "10%",
    width: 160,
    height: 360,
    color: "var(--color-accent)",
    delay: 3.2,
  },
  {
    d: "M80 0 L50 120 L100 130 L30 300",
    bottom: "-5%",
    left: "40%",
    width: 150,
    height: 320,
    color: "var(--color-primary)",
    delay: 6.5,
  },
];

function LightningBolt({ bolt }: { bolt: (typeof bolts)[number] }) {
  return (
    <motion.svg
      className="absolute opacity-0"
      style={{
        top: bolt.top,
        left: bolt.left,
        right: bolt.right,
        bottom: bolt.bottom,
        filter: `drop-shadow(0 0 8px ${bolt.color}) drop-shadow(0 0 20px ${bolt.color})`,
      }}
      width={bolt.width}
      height={bolt.height}
      viewBox="0 0 160 400"
      fill="none"
      animate={{ opacity: [0, 0.9, 0.2, 0.8, 0, 0] }}
      transition={{
        duration: 0.6,
        times: [0, 0.1, 0.2, 0.3, 0.4, 1],
        repeat: Infinity,
        repeatDelay: 7 + bolt.delay,
        delay: bolt.delay,
        ease: "easeOut",
      }}
    >
      <path d={bolt.d} stroke={bolt.color} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
    </motion.svg>
  );
}

/**
 * Purely decorative, absolutely-positioned glow blobs + flickering neon
 * lightning behind the dashboard content. Pointer-events are disabled so it
 * never blocks clicks, and it respects prefers-reduced-motion via the
 * global rule in globals.css. No data, no props needed — safe to drop into
 * any layout.
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

      {/* Neon electric flickers */}
      {bolts.map((bolt, i) => (
        <LightningBolt key={i} bolt={bolt} />
      ))}

      {/* Thin pulsing neon scan-line for extra "electric" ambience */}
      <motion.div
        className="absolute inset-x-0 h-px"
        style={{
          top: "35%",
          background: "linear-gradient(90deg, transparent, var(--color-primary), transparent)",
          filter: "drop-shadow(0 0 6px var(--color-primary))",
        }}
        animate={{ opacity: [0, 0.5, 0], x: ["-10%", "10%", "-10%"] }}
        transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
}