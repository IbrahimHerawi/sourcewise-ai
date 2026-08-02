import type { ReactNode } from "react";
import { CircleAlert, FileUp, MessageCircleQuestion, TriangleAlert, X } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { CollectionButton } from "../collection-button";
import styles from "./collection-detail.module.css";

type StateCardProps = {
  action: ReactNode;
  description: string;
  icon: ReactNode;
  id: string;
  title: string;
  tone?: "default" | "error";
};

function CollectionDetailStateCard({
  action,
  description,
  icon,
  id,
  title,
  tone = "default",
}: StateCardProps) {
  return (
    <section
      aria-labelledby={id}
      className={cn(styles.stateCard, tone === "error" && styles.errorStateCard)}
      role={tone === "error" ? "alert" : "region"}
    >
      <div className={styles.stateIcon}>{icon}</div>
      <h2 id={id}>{title}</h2>
      <p>{description}</p>
      {action}
    </section>
  );
}

export function CollectionDetailEmptyState({ onUpload }: { onUpload: () => void }) {
  return (
    <CollectionDetailStateCard
      action={<CollectionButton onClick={onUpload}>Upload to collection</CollectionButton>}
      description="Upload documents to start asking grounded questions."
      icon={<FileUp aria-hidden="true" />}
      id="empty-collection-title"
      title="This collection is empty"
    />
  );
}

export function NoQuestionHistoryState({
  canAsk,
  onAsk,
}: {
  canAsk: boolean;
  onAsk: () => void;
}) {
  return (
    <CollectionDetailStateCard
      action={
        <CollectionButton disabled={!canAsk} onClick={onAsk}>
          Ask this collection
        </CollectionButton>
      }
      description="Ask this collection to create its first grounded answer."
      icon={<MessageCircleQuestion aria-hidden="true" />}
      id="no-question-history-title"
      title="No question history"
    />
  );
}

export function NoReadyDocumentsWarning({
  onDismiss,
}: {
  onDismiss: () => void;
}) {
  return (
    <aside className={styles.warning} role="status">
      <TriangleAlert aria-hidden="true" />
      <p>No ready documents. Processing must finish before you can ask this collection.</p>
      <button
        aria-label="Dismiss processing warning"
        className={styles.warningDismiss}
        onClick={onDismiss}
        type="button"
      >
        <X aria-hidden="true" />
      </button>
    </aside>
  );
}

export function CollectionDetailErrorState({
  kind,
  onAction,
}: {
  kind: "not-found" | "server-error";
  onAction: () => void;
}) {
  const notFound = kind === "not-found";
  return (
    <div className={styles.errorStatePosition}>
      <CollectionDetailStateCard
        action={
          <CollectionButton onClick={onAction} tone="solid-danger">
            {notFound ? "Back to Collections" : "Try again"}
          </CollectionButton>
        }
        description={
          notFound
            ? "The collection may have been deleted or the link may be outdated."
            : "A server error prevented this collection from loading. Try again."
        }
        icon={<CircleAlert aria-hidden="true" />}
        id={`collection-${kind}-title`}
        title={notFound ? "Collection not found" : "Collection couldn’t load"}
        tone="error"
      />
    </div>
  );
}

function SkeletonLine({ className }: { className: string }) {
  return <Skeleton className={cn(styles.skeletonLine, className)} />;
}

function SkeletonRows({ count = 3 }: { count?: number }) {
  return (
    <div className={styles.skeletonRows}>
      {Array.from({ length: count }, (_, index) => (
        <div className={styles.skeletonRow} key={index}>
          <SkeletonLine className={styles.skeletonRowTitle} />
          <SkeletonLine className={styles.skeletonRowMetadata} />
          <SkeletonLine className={styles.skeletonBadge} />
        </div>
      ))}
    </div>
  );
}

export function CollectionDetailSkeleton() {
  return (
    <div aria-busy="true" aria-live="polite" className={styles.skeletonLayout}>
      <span className="sr-only">Loading collection details</span>
      <div aria-hidden="true" className={styles.skeletonSummary}>
        <div>
          <SkeletonLine className={styles.skeletonMetric} />
          <SkeletonLine className={styles.skeletonMetricLabel} />
        </div>
        <div>
          <SkeletonLine className={styles.skeletonMetric} />
          <SkeletonLine className={styles.skeletonMetricLabel} />
        </div>
        <SkeletonLine className={styles.skeletonActions} />
      </div>
      <div aria-hidden="true" className={styles.skeletonTabs}>
        <SkeletonLine className={styles.skeletonTab} />
        <SkeletonLine className={styles.skeletonTab} />
      </div>
      <div aria-hidden="true" className={styles.skeletonSection}>
        <SkeletonLine className={styles.skeletonSectionTitle} />
        <SkeletonLine className={styles.skeletonSectionCount} />
      </div>
      <div aria-hidden="true" className={styles.skeletonTables}>
        <SkeletonRows />
        <SkeletonRows />
      </div>
    </div>
  );
}
