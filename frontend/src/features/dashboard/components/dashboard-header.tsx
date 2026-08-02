"use client";

import type { RefObject } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  getDashboardParentRoute,
  resolveDashboardBackHref,
  resolveDashboardRoute,
} from "@/features/dashboard/navigation";
import { useScrollShadow } from "@/features/dashboard/hooks/use-scroll-shadow";
import { useRegisteredDashboardHeader } from "./dashboard-header-context";
import styles from "./dashboard-header.module.css";

type DashboardHeaderProps = {
  scrollContainerRef: RefObject<HTMLElement | null>;
};

export function DashboardHeader({
  scrollContainerRef,
}: DashboardHeaderProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const route = resolveDashboardRoute(pathname);
  const parent = getDashboardParentRoute(route);
  const registeredHeader = useRegisteredDashboardHeader();
  const routeHeader =
    registeredHeader?.pathname === pathname ? registeredHeader : null;
  const isScrolled = useScrollShadow(scrollContainerRef);
  const title = routeHeader?.title ?? route?.headerTitle ?? "Dashboard";
  const contextualLabel =
    routeHeader?.contextualLabel ?? route?.contextualLabel;
  const backHref = parent
    ? resolveDashboardBackHref(searchParams?.get("returnTo"), parent.href)
    : undefined;

  return (
    <header
      className={cn(styles.header, isScrolled && styles.headerScrolled)}
      data-scrolled={isScrolled ? "true" : "false"}
      data-slot="dashboard-header"
    >
      <div className={styles.inner}>
        <div className={styles.identity}>
          {parent && backHref ? (
            <Link
              aria-label={`Back to ${parent.headerTitle}`}
              className={styles.backLink}
              href={backHref}
            >
              <ArrowLeft aria-hidden="true" />
              <span>{parent.headerTitle}</span>
            </Link>
          ) : contextualLabel ? (
            <span className={styles.contextualLabel}>{contextualLabel}</span>
          ) : null}
          <h1 className={styles.title}>{title}</h1>
        </div>
        {routeHeader?.actions ? (
          <div className={styles.actions} data-slot="dashboard-header-actions">
            {routeHeader.actions}
          </div>
        ) : null}
      </div>
    </header>
  );
}
