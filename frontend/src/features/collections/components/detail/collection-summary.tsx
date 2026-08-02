import { CollectionButton } from "../collection-button";
import styles from "./collection-detail.module.css";

type CollectionSummaryProps = {
  documentTotal: number;
  questionTotal: number;
  onAsk: () => void;
  onDelete: (opener: HTMLButtonElement) => void;
  onEdit: (opener: HTMLButtonElement) => void;
};

export function CollectionSummary({
  documentTotal,
  onAsk,
  onDelete,
  onEdit,
  questionTotal,
}: CollectionSummaryProps) {
  return (
    <section aria-label="Collection summary" className={styles.summary}>
      <dl className={styles.metrics}>
        <div className={styles.metric}>
          <dd>{documentTotal.toLocaleString()}</dd>
          <dt>Documents</dt>
        </div>
        <div className={styles.metric}>
          <dd>{questionTotal.toLocaleString()}</dd>
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
        <CollectionButton onClick={onAsk} shape="pill">
          Ask this collection
        </CollectionButton>
      </div>
    </section>
  );
}
