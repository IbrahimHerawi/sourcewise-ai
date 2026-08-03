import { CircleAlert, FileUp } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { CollectionButton } from "@/features/collections/components/collection-button";
import styles from "./documents-page.module.css";

export function DocumentsEmptyState({ onChooseFiles }: { onChooseFiles: () => void }) {
  return (
    <section aria-labelledby="documents-empty-title" className={styles.messageState}>
      <span className={styles.stateIconHalo}>
        <FileUp aria-hidden="true" />
      </span>
      <h2 id="documents-empty-title">No documents yet</h2>
      <p>Upload up to three files to start building your source library.</p>
      <CollectionButton onClick={onChooseFiles} type="button">
        Choose files
      </CollectionButton>
    </section>
  );
}

export function DocumentsZeroResultsState({
  collectionName,
  onShowAll,
}: {
  collectionName: string;
  onShowAll: () => void;
}) {
  const conciseCollectionName =
    collectionName.replace(/\s+collection$/i, "").trim() || collectionName;

  return (
    <section aria-labelledby="documents-zero-title" className={styles.messageState}>
      <span aria-hidden="true" className={styles.zeroResultsHalo}>
        0
      </span>
      <h2 id="documents-zero-title">
        No documents in {conciseCollectionName}
      </h2>
      <p>This collection has no documents. Choose another collection or show all documents.</p>
      <CollectionButton onClick={onShowAll} tone="secondary" type="button">
        Show all documents
      </CollectionButton>
    </section>
  );
}

export function DocumentsErrorState({
  description,
  onRetry,
  title,
}: {
  description: string;
  onRetry: () => void;
  title: string;
}) {
  return (
    <section aria-labelledby="documents-error-title" className={styles.pageErrorState}>
      <span className={styles.errorIconHalo}>
        <CircleAlert aria-hidden="true" />
      </span>
      <h2 id="documents-error-title">{title}</h2>
      <p>{description}</p>
      <CollectionButton onClick={onRetry} type="button">
        Try loading again
      </CollectionButton>
    </section>
  );
}

export function DocumentsRefreshNotice({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className={styles.refreshNotice} role="status">
      <CircleAlert aria-hidden="true" />
      <p>{message}</p>
      <button onClick={onRetry} type="button">
        Refresh now
      </button>
    </div>
  );
}

function SkeletonRow({ width }: { width: string }) {
  return (
    <li className={styles.skeletonRow}>
      <Skeleton className={styles.skeletonExtension} />
      <Skeleton className={styles.skeletonFilename} style={{ width }} />
      <Skeleton className={styles.skeletonRowMetadata} />
      <Skeleton className={styles.skeletonStatus} />
      <Skeleton className={styles.skeletonActions} />
    </li>
  );
}

export function DocumentsSkeleton() {
  return (
    <section aria-busy="true" aria-labelledby="documents-loading-label">
      <h2 className={styles.libraryTitle} id="documents-loading-label">
        Loading documents…
      </h2>
      <span className="sr-only">The document library is loading.</span>
      <ul aria-hidden="true" className={styles.documentSurface}>
        <SkeletonRow width="58%" />
        <SkeletonRow width="72%" />
        <SkeletonRow width="64%" />
        <SkeletonRow width="78%" />
      </ul>
    </section>
  );
}
