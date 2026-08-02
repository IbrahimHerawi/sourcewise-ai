import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";
import styles from "./dashboard-page.module.css";

type DashboardPageProps = HTMLAttributes<HTMLDivElement>;

/** Shared symmetrical content container for dashboard navigation pages. */
export function DashboardPage({ className, ...props }: DashboardPageProps) {
  return <div className={cn(styles.page, className)} {...props} />;
}
