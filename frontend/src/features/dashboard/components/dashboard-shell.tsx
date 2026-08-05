"use client";

import { useRef, type ReactNode } from "react";
import { Inter } from "next/font/google";
import { useDashboardScrollRestoration } from "@/features/dashboard/hooks/use-dashboard-scroll-restoration";
import { DashboardHeader } from "./dashboard-header";
import { DashboardHeaderProvider } from "./dashboard-header-context";
import { DashboardMobileNavigation } from "./dashboard-mobile-navigation";
import { DashboardSidebar } from "./dashboard-sidebar";
import styles from "./dashboard-shell.module.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

type DashboardShellProps = {
  children: ReactNode;
};

function DashboardShellContent({ children }: DashboardShellProps) {
  const contentRef = useRef<HTMLElement>(null);
  useDashboardScrollRestoration(contentRef);

  return (
    <div className={`${styles.shell} ${inter.variable}`} data-slot="dashboard-shell">
      <a className={styles.skipLink} href="#dashboard-main-content">
        Skip to main content
      </a>
      <DashboardSidebar />
      <div className={styles.mainRegion} data-slot="dashboard-main-region">
        <DashboardMobileNavigation />
        <DashboardHeader scrollContainerRef={contentRef} />
        <main
          aria-label="Dashboard content"
          className={styles.content}
          data-slot="dashboard-content"
          id="dashboard-main-content"
          ref={contentRef}
          tabIndex={0}
        >
          {children}
        </main>
      </div>
    </div>
  );
}

/** Shared viewport shell for every authenticated dashboard surface. */
export function DashboardShell({ children }: DashboardShellProps) {
  return (
    <DashboardHeaderProvider>
      <DashboardShellContent>{children}</DashboardShellContent>
    </DashboardHeaderProvider>
  );
}
