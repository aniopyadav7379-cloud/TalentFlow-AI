"use client";

import { motion } from "framer-motion";

/**
 * Self-built equivalent of a "pulsing circle" Lottie animation — concentric
 * neon rings that expand and fade outward, like a radar ping. No external
 * file or npm package needed (LottieFiles gates free JSON downloads behind
 * login on many animations), and it automatically matches the app's
 * indigo/purple theme via CSS variables instead of a hardcoded color.
 *
 * Pointer-events disabled so it never blocks clicks.
 */
const rings = [0, 1.3, 2.6, 3.9];

export function CirclePulseBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 -z-20 flex items-center justify-center overflow-hidden">
      {rings.map((delay, i) => (
        <motion.div
          key={i}
          className="absolute rounded-full border"
          style={{
            borderColor: "var(--color-primary)",
            boxShadow: "0 0 24px var(--color-primary), inset 0 0 24px var(--color-primary)",
          }}
          initial={{ width: 40, height: 40, opacity: 0.6 }}
          animate={{ width: "70vmin", height: "70vmin", opacity: 0 }}
          transition={{
            duration: 5.2,
            repeat: Infinity,
            delay,
            ease: "easeOut",
          }}
        />
      ))}
      {/* Steady glowing core so the rings have a visible origin point */}
      <motion.div
        className="absolute h-4 w-4 rounded-full"
        style={{ background: "var(--color-accent)", boxShadow: "0 0 30px 10px var(--color-accent)" }}
        animate={{ opacity: [0.4, 0.9, 0.4], scale: [1, 1.3, 1] }}
        transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
      />
    </div>
  );
}