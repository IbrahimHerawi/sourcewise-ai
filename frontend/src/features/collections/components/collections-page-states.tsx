import type { ReactNode } from "react";
import { CircleAlert, Folder, Plus } from "lucide-react";
import { cn } from "@/lib/utils";
import { CollectionButton } from "./collection-button";
import { CollectionsListLoading } from "./collection-list";
import styles from "./collections-page-states.module.css";

type CollectionsMessageStateProps = {
  action: ReactNode;
  description: string;
  icon: ReactNode;
  id: string;
  tone?: "default" | "error";
  title: string;
};

function CollectionsMessageState({
  action,
  description,
  icon,
  id,
  tone = "default",
  title,
}: CollectionsMessageStateProps) {
  const isError = tone === "error";

  return (
    <section
      aria-labelledby={id}
      className={cn(styles.messagePanel, isError && styles.errorPanel)}
    >
      <div
        className={cn(
          styles.iconHalo,
          isError ? styles.errorHalo : styles.emptyHalo,
        )}
      >
        {icon}
      </div>
      <h2 className={isError ? styles.errorTitle : styles.messageTitle} id={id}>
        {title}
      </h2>
      <p className={styles.messageBody}>{description}</p>
      {action}
    </section>
  );
}

export function CollectionsLoadingState() {
  return <CollectionsListLoading />;
}

export function CollectionsErrorState({
  message = "A server error prevented collections from loading. Try again.",
  onRetry,
}: {
  message?: string;
  onRetry: () => void;
}) {
  return (
    <CollectionsMessageState
      action={<CollectionButton onClick={onRetry}>Retry</CollectionButton>}
      description={message}
      icon={<CircleAlert aria-hidden="true" className={styles.stateIcon} />}
      id="collections-error-title"
      title="Collections couldn’t load"
      tone="error"
    />
  );
}

export function CollectionsEmptyState({
  onCreate,
}: {
  onCreate: (opener: HTMLButtonElement) => void;
}) {
  return (
    <CollectionsMessageState
      action={
        <CollectionButton onClick={(event) => onCreate(event.currentTarget)}>
          <Plus aria-hidden="true" />
          Create Collection
        </CollectionButton>
      }
      description="Create your first collection to organize documents by project, client, or topic."
      icon={<Folder aria-hidden="true" className={styles.stateIcon} />}
      id="collections-empty-title"
      title="No collections yet"
    />
  );
}

export function CollectionNotFoundState({ onBack }: { onBack: () => void }) {
  return (
    <CollectionsMessageState
      action={<CollectionButton onClick={onBack}>Back to Collections</CollectionButton>}
      description="This collection may have been deleted or you may no longer have access."
      icon={<Folder aria-hidden="true" className={styles.stateIcon} />}
      id="collection-not-found-title"
      title="Collection not found"
    />
  );
}
