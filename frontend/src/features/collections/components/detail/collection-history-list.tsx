import type { CollectionHistoryItem } from "@/features/collections/collection-detail-types";
import styles from "./collection-detail.module.css";

export function CollectionHistoryCard({
  item,
}: {
  item: CollectionHistoryItem;
}) {
  return (
    <li>
      <article className={styles.historyCard}>
        <h3>{item.question}</h3>
        <p className={styles.answer}>{item.answer}</p>
        <div className={styles.historyMetadata}>
          <span className={styles.citationBadge}>
            {item.citationCount} {item.citationCount === 1 ? "citation" : "citations"}
          </span>
          <time>{item.askedAt}</time>
        </div>
      </article>
    </li>
  );
}

export function CollectionHistoryList({
  items,
}: {
  items: readonly CollectionHistoryItem[];
}) {
  return (
    <ul className={styles.historyList}>
      {items.map((item) => (
        <CollectionHistoryCard item={item} key={item.id} />
      ))}
    </ul>
  );
}
