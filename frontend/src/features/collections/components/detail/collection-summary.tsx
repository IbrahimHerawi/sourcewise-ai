import type { CollectionDetail } from "@/features/collections/collection-detail-types";
import { CollectionButton } from "../collection-button";
import styles from "./collection-detail.module.css";

type CollectionSummaryProps = {
  collection: CollectionDetail;
  onAsk: () => void;
  onDelete: (opener: HTMLButtonElement) => void;
  onEdit: (opener: HTMLButtonElement) => void;
};

export function CollectionSummary({
  collection,
  onAsk,
  onDelete,
  onEdit,
}: CollectionSummaryProps) {
  const canAsk = collection.readyDocumentCount > 0;

  return (
    <section aria-label="Collection summary" className={styles.summary}>
      <dl className={styles.metrics}>
        <div className={styles.metric}>
          <dd>{collection.documentTotal}</dd>
          <dt>Documents</dt>
        </div>
        <div className={styles.metric}>
          <dd>{collection.questionTotal}</dd>
          <dt>Questions</dt>
        </div>
      </dl>
      <div className={styles.actions}>
        <CollectionButton
          onClick={(event) => onDelete(event.currentTarget)}
          shape="pill"
          tone="solid-danger"
        >
          Delete
        </CollectionButton>
        <CollectionButton
          onClick={(event) => onEdit(event.currentTarget)}
          shape="pill"
          tone="outline"
        >
          Edit
        </CollectionButton>
        <CollectionButton disabled={!canAsk} onClick={onAsk} shape="pill">
          Ask this collection
        </CollectionButton>
      </div>
    </section>
  );
}
