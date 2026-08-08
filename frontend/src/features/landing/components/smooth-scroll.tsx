"use client";

import * as React from "react";
import Lenis from "lenis";

// Module-level singleton so other components (e.g. the navbar) can drive
// Lenis for programmatic smooth-scrolls (anchor links) via `scrollToElement`.
let lenisInstance: Lenis | null = null;

/**
 * Smoothly scroll to an element (by CSS selector or element). The same
 * interpolation used for wheel input is used for anchors, so navigation stays
 * interruptible and does not impose a fixed-duration wait on short jumps.
 */
export function scrollToElement(target: string | HTMLElement) {
  const el = typeof target === "string" ? document.querySelector(target) : target;
  if (!el) return;
  if (lenisInstance) {
    lenisInstance.scrollTo(el as HTMLElement, {
      offset: 0,
      lerp: 0.18,
      lock: false,
    });
  } else {
    const behavior = window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "auto"
      : "smooth";
    (el as HTMLElement).scrollIntoView({ behavior, block: "start" });
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
    const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
    let lenis: Lenis | null = null;

    const destroy = () => {
      lenis?.destroy();
      if (lenisInstance === lenis) lenisInstance = null;
      lenis = null;
    };

    const configure = () => {
      destroy();
      if (motionPreference.matches) return;

      lenis = new Lenis({
        // A short exponential tail filters wheel steps without putting a
        // noticeable delay between the gesture and the page.
        lerp: 0.18,
        smoothWheel: true,
        wheelMultiplier: 1,
        // Preserve direct, platform-native touch tracking and momentum.
        syncTouch: false,
        touchMultiplier: 1,
        autoRaf: true,
      });
      lenisInstance = lenis;
    };

    configure();
    motionPreference.addEventListener?.("change", configure);

    return () => {
      motionPreference.removeEventListener?.("change", configure);
      destroy();
    };
  }, []);

  return <>{children}</>;
}
