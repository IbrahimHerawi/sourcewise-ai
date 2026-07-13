"use client";

import * as React from "react";
import Lenis from "lenis";

// Module-level singleton so other components (e.g. the navbar) can drive
// Lenis for programmatic smooth-scrolls (anchor links) via `scrollToElement`.
let lenisInstance: Lenis | null = null;

/**
 * Smoothly scroll to an element (by CSS selector or element). Uses Lenis when
 * available for a fluid glide; falls back to native scrollIntoView otherwise.
 */
export function scrollToElement(target: string | HTMLElement) {
  const el = typeof target === "string" ? document.querySelector(target) : target;
  if (!el) return;
  if (lenisInstance) {
    lenisInstance.scrollTo(el as HTMLElement, { offset: 0, duration: 1.2 });
  } else {
    (el as HTMLElement).scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

/** Stop Lenis smooth-scrolling (e.g. when a modal opens). */
export function stopScroll() {
  lenisInstance?.stop();
}

/** Resume Lenis smooth-scrolling (e.g. when a modal closes). */
export function startScroll() {
  lenisInstance?.start();
}

/**
 * SmoothScroll
 *
 * Wraps the app with Lenis-based smooth scrolling for a fluid, premium scroll
 * feel (eases the scroll position toward the target on each frame instead of
 * the native abrupt step-jumps). Keeps the same total scroll distance — only
 * the motion becomes smoother.
 *
 * Lenis preserves the native scroll APIs (window.scrollY, getBoundingClientRect,
 * position: sticky), so scroll-driven animations (sticky scrollytelling,
 * particle field, navbar hide/show) continue to work correctly.
 *
 * Respects prefers-reduced-motion: when set, Lenis is not initialized and the
 * page uses native scrolling.
 */
export function SmoothScroll({ children }: { children: React.ReactNode }) {
  React.useEffect(() => {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion) return;

    const lenis = new Lenis({
      // How fast the scroll eases toward the target. Lower = smoother/longer
      // glide; higher = snappier/more responsive. 0.18 makes the scroll feel
      // light and closely tied to the input (minimal lag) while still smooth.
      // Lenis's lerp is an exponential ease-out, so the motion always
      // decelerates naturally toward the target — never stops abruptly.
      lerp: 0.18,
      smoothWheel: true,
      // Slightly tamer touch scrolling for mobile.
      smoothTouch: false,
      // A touch more distance per wheel notch so less physical scrolling is
      // needed to move the content.
      wheelMultiplier: 1.1,
      touchMultiplier: 1.5,
    });
    lenisInstance = lenis;

    let rafId = 0;
    const raf = (time: number) => {
      lenis.raf(time);
      rafId = requestAnimationFrame(raf);
    };
    rafId = requestAnimationFrame(raf);

    return () => {
      cancelAnimationFrame(rafId);
      lenis.destroy();
      lenisInstance = null;
    };
  }, []);

  return <>{children}</>;
}

