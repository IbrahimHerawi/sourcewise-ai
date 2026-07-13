"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ParticleField } from "./particle-field";
import { Typewriter } from "./typewriter";

const ease = [0.22, 1, 0.36, 1] as const;

export function Hero({ onOpenAuth }: { onOpenAuth: (tab: "signin" | "signup") => void }) {
  // The headline typewriter runs first; the buttons fade in (opacity only — no
  // layout shift) after the typewriter finishes. The button container is
  // always rendered so its space is reserved from the start.
  const [headlineDone, setHeadlineDone] = React.useState(false);

  return (
    <section
      id="top"
      className="relative isolate flex min-h-[100svh] items-center justify-center overflow-hidden pt-28 pb-20"
    >
      {/* Particle field on a pure-white canvas (no grid/gradient overlays) */}
      <ParticleField className="absolute inset-0 -z-10 h-full w-full" />

      <div className="mx-auto w-full max-w-4xl px-5 text-center">
        {/* Headline — typewriter effect first. reserveHeight keeps the layout
            stable (no shift as the text grows from 1 line to 2 lines). */}
        <motion.h1
          initial={{ opacity: 0, y: 22 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease }}
          className="mx-auto mt-6 max-w-4xl text-balance text-center tracking-tight"
          style={{ fontSize: "clamp(1.6rem, 4.9vw, 3.5rem)", fontWeight: 450, lineHeight: 1.1 }}
        >
          <Typewriter
            text="Chat with your documents Powered by AI"
            highlight="Powered by AI"
            highlightClassName="text-gradient-brand"
            breakBeforeHighlight
            reserveHeight
            onDone={() => setHeadlineDone(true)}
          />
        </motion.h1>

        {/* CTAs — always rendered (space reserved from the start). Only opacity
            animates (no y translate) so there is ZERO layout shift when the
            buttons appear after the typewriter finishes. */}
        <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: headlineDone ? 1 : 0 }}
            transition={{ duration: 0.6, ease, delay: 0.15 }}
            className="flex flex-col items-center justify-center gap-3 sm:flex-row"
            style={{ pointerEvents: headlineDone ? "auto" : "none" }}
          >
            <Button
              size="lg"
              onClick={() => onOpenAuth("signup")}
              className="bg-brand-gradient group h-12 rounded-xl px-7 text-sm font-medium hover:opacity-95"
            >
              Get Started
              <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
            </Button>
            <Button
              size="lg"
              variant="outline"
              onClick={() => onOpenAuth("signin")}
              className="h-12 rounded-xl border-border bg-white px-7 text-sm font-medium hover:bg-muted"
            >
              Sign In
            </Button>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
