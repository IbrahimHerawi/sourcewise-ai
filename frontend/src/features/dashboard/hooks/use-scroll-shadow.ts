"use client";

import { useEffect, useState, type RefObject } from "react";

/** Tracks only the threshold needed to elevate a stationary shell header. */
export function useScrollShadow(
  scrollContainerRef: RefObject<HTMLElement | null>,
): boolean {
  const [isScrolled, setIsScrolled] = useState(false);

  useEffect(() => {
    const scrollContainer = scrollContainerRef.current;
    if (!scrollContainer) return;

    const update = () => {
      const nextIsScrolled = scrollContainer.scrollTop > 0;
      setIsScrolled((current) =>
        current === nextIsScrolled ? current : nextIsScrolled,
      );
    };

    update();
    scrollContainer.addEventListener("scroll", update, { passive: true });
    return () => scrollContainer.removeEventListener("scroll", update);
  }, [scrollContainerRef]);

  return isScrolled;
}
