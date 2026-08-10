"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, type RefObject } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { resolveDashboardRoute } from "@/features/dashboard/navigation";

const dashboardScrollPositions = new Map<string, number>();

function createScrollKey(pathname: string, search: string): string {
  const route = resolveDashboardRoute(pathname);

  // Detail tabs share a viewport; list query state remains independently keyed.
  if (route?.id === "collection-detail") return pathname;
  return search ? `${pathname}?${search}` : pathname;
}

/** Restores the custom dashboard viewport because the document does not scroll. */
export function useDashboardScrollRestoration(
  scrollContainerRef: RefObject<HTMLElement | null>,
): void {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const search = searchParams?.toString() ?? "";
  const scrollKey = useMemo(
    () => createScrollKey(pathname, search),
    [pathname, search],
  );
  const activeKeyRef = useRef(scrollKey);

  useLayoutEffect(() => {
    const scrollContainer = scrollContainerRef.current;
    if (!scrollContainer) return;

    const previousKey = activeKeyRef.current;
    if (previousKey !== scrollKey) {
      dashboardScrollPositions.set(previousKey, scrollContainer.scrollTop);
      activeKeyRef.current = scrollKey;
    }

    scrollContainer.scrollTop = dashboardScrollPositions.get(scrollKey) ?? 0;
  }, [scrollContainerRef, scrollKey]);

  useEffect(() => {
    const scrollContainer = scrollContainerRef.current;
    if (!scrollContainer) return;

    const savePosition = () => {
      dashboardScrollPositions.set(
        activeKeyRef.current,
        scrollContainer.scrollTop,
      );
    };

    scrollContainer.addEventListener("scroll", savePosition, { passive: true });
    return () => {
      savePosition();
      scrollContainer.removeEventListener("scroll", savePosition);
    };
  }, [scrollContainerRef]);
}
