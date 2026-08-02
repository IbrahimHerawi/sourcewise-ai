import type { ReactNode } from "react";
import { DashboardPage } from "@/features/dashboard/components/dashboard-page";
import styles from "./collection-detail.module.css";

type CollectionDetailLayoutProps = {
  children: ReactNode;
};

export function CollectionDetailLayout({ children }: CollectionDetailLayoutProps) {
  return (
    <DashboardPage>
      <div className={styles.screen}>
        <div className={styles.detailContent}>{children}</div>
      </div>
    </DashboardPage>
  );
}
