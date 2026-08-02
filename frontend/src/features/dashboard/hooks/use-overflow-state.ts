"use client";

import { useLayoutEffect, useState, type RefObject } from "react";

/** Enables an internal scrollbar only after the region genuinely overflows. */
export function useOverflowState(
  regionRef: RefObject<HTMLElement | null>,
): boolean {
  const [isOverflowing, setIsOverflowing] = useState(false);

  useLayoutEffect(() => {
    const region = regionRef.current;
    if (!region) return;

    const update = () => {
      const nextIsOverflowing = region.scrollHeight > region.clientHeight + 1;
      setIsOverflowing((current) =>
        current === nextIsOverflowing ? current : nextIsOverflowing,
      );
    };

    update();
    window.addEventListener("resize", update);

    const observer =
      typeof ResizeObserver === "undefined" ? null : new ResizeObserver(update);
    observer?.observe(region);

    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", update);
    };
  }, [regionRef]);

  return isOverflowing;
}
