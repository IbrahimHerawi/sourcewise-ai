import Link from "next/link";
import { Skeleton } from "@/components/ui/skeleton";
import { appendDashboardReturnTo } from "@/features/dashboard/navigation";
import type { CollectionApiRecord } from "@/features/collections/collections-api-types";
import { formatDateTime } from "@/features/collections/collection-formatters";
import { CollectionButton } from "./collection-button";
import styles from "./collection-list.module.css";

type CollectionAction = (
  collection: CollectionApiRecord,
  opener: HTMLButtonElement,
) => void;

type CollectionListProps = {
  collections: readonly CollectionApiRecord[];
  currentPage: number;
  onPageChange: (page: number) => void;
  onDelete: CollectionAction;
  onEdit: CollectionAction;
  returnTo: string;
};

function CollectionRow({
  collection,
  onDelete,
  onEdit,
  returnTo,
}: {
  collection: CollectionApiRecord;
  onDelete: CollectionAction;
  onEdit: CollectionAction;
  returnTo: string;
}) {
  return (
    <li>
      <article className={styles.collectionCard}>
        <div className={styles.cardHeader}>
          <div className={styles.collectionInformation}>
            <h2 className={styles.collectionName}>
              <Link
                href={appendDashboardReturnTo(
                  `/dashboard/collections/${collection.id}`,
                  returnTo,
                )}
              >
                {collection.name}
              </Link>
            </h2>
            {collection.description ? (
              <p className={styles.collectionDescription}>{collection.description}</p>
            ) : null}
          </div>
          <div className={styles.cardActions}>
            <CollectionButton
              onClick={(event) => onEdit(collection, event.currentTarget)}
              tone="secondary"
            >
              Edit
            </CollectionButton>
            <CollectionButton
              onClick={(event) => onDelete(collection, event.currentTarget)}
              tone="danger"
            >
              Delete
            </CollectionButton>
          </div>
        </div>
        <div className={styles.metadata}>
          <span>Created {formatDateTime(collection.created_at)}</span>
          <span aria-hidden="true">•</span>
          <span>Updated {formatDateTime(collection.updated_at)}</span>
        </div>
      </article>
    </li>
  );
}

export function CollectionsList({
  collections,
  currentPage,
  onDelete,
  onEdit,
  onPageChange,
  pageCount,
  returnTo,
}: CollectionListProps & { pageCount: number }) {
  return (
    <>
      <ul className={styles.collectionList}>
        {collections.map((collection) => (
          <CollectionRow
            collection={collection}
            key={collection.id}
            onDelete={onDelete}
            onEdit={onEdit}
            returnTo={returnTo}
          />
        ))}
      </ul>
      <nav aria-label="Collections pagination" className={styles.pagination}>
        <p>
          Page {currentPage.toLocaleString()} of {pageCount.toLocaleString()}
        </p>
        <div className={styles.paginationControls}>
          <CollectionButton
            disabled={currentPage <= 1}
            onClick={() => onPageChange(currentPage - 1)}
            tone="secondary"
          >
            Previous
          </CollectionButton>
          <CollectionButton
            disabled={currentPage >= pageCount}
            onClick={() => onPageChange(currentPage + 1)}
          >
            Next
          </CollectionButton>
        </div>
      </nav>
    </>
  );
}

function LoadingRow() {
  return (
    <li className={styles.loadingCard}>
      <Skeleton className={`${styles.skeleton} ${styles.skeletonName}`} />
      <Skeleton className={`${styles.skeleton} ${styles.skeletonDescription}`} />
      <Skeleton className={`${styles.skeleton} ${styles.skeletonMetadata}`} />
    </li>
  );
}

export function CollectionsListLoading() {
  return (
    <div aria-busy="true" aria-live="polite">
      <span className="sr-only">Loading collections</span>
      <ul aria-hidden="true" className={styles.collectionList}>
        {Array.from({ length: 4 }, (_, index) => (
          <LoadingRow key={index} />
        ))}
      </ul>
      <div className={styles.pagination}>
        <p>Loading collections...</p>
      </div>
    </div>
  );
}
