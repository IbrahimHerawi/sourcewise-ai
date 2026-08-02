import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";
import styles from "./dashboard-page.module.css";

type DashboardPageProps = HTMLAttributes<HTMLDivElement>;

type DashboardPageHeaderProps = {
  title: string;
  action?: ReactNode;
  description?: string;
};

/** Shared symmetrical content container for dashboard navigation pages. */
export function DashboardPage({ className, ...props }: DashboardPageProps) {
  return <div className={cn(styles.page, className)} {...props} />;
}

/** Shared dashboard page-title row with an optional primary action. */
export function DashboardPageHeader({
  title,
  action,
  description,
}: DashboardPageHeaderProps) {
  return (
    <header className={styles.header}>
      <div className={styles.titleGroup}>
        <h1 className={styles.title}>{title}</h1>
        {description ? <p className={styles.description}>{description}</p> : null}
      </div>
      {action ? <div className={styles.action}>{action}</div> : null}
    </header>
  );
}
