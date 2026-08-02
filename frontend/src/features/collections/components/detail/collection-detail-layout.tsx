import type { ReactNode } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { DashboardPage } from "@/features/dashboard/components/dashboard-page";
import { CollectionButton } from "../collection-button";
import styles from "./collection-detail.module.css";

type CollectionDetailLayoutProps = {
  children: ReactNode;
  isLoading?: boolean;
  onUpload?: () => void;
  title?: string;
};

export function CollectionDetailLayout({
  children,
  isLoading = false,
  onUpload,
  title,
}: CollectionDetailLayoutProps) {
  return (
    <DashboardPage>
      <div className={styles.screen}>
        <header className={styles.pageHeader}>
          {isLoading ? (
            <Skeleton aria-hidden="true" className={styles.headerTitleSkeleton} />
          ) : (
            <h1 className={styles.pageTitle}>{title ?? "Collection"}</h1>
          )}
          {isLoading ? (
            <Skeleton aria-hidden="true" className={styles.headerActionSkeleton} />
          ) : onUpload ? (
            <CollectionButton onClick={onUpload} shape="pill">
              Upload to collection
            </CollectionButton>
          ) : null}
        </header>
        <div className={styles.detailContent}>{children}</div>
      </div>
    </DashboardPage>
  );
}
