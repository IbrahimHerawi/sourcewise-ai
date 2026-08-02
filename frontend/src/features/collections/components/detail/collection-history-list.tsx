import { MoreHorizontal, Trash2 } from "lucide-react";
import type { QuestionHistoryItem } from "@/features/collections/collections-api-types";
import { formatRelativeDate } from "@/features/collections/collection-formatters";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import styles from "./collection-detail.module.css";

export function CollectionHistoryCard({
  item,
  onDelete,
  onViewDetails,
}: {
  item: QuestionHistoryItem;
  onDelete: (item: QuestionHistoryItem) => void;
  onViewDetails: (item: QuestionHistoryItem) => void;
}) {
  return (
    <li>
      <article className={styles.historyCard}>
        <div className={styles.historyCardHeader}>
          <button
            className={styles.historyTitleButton}
            onClick={() => onViewDetails(item)}
            type="button"
          >
            <h3>{item.question}</h3>
          </button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                aria-label={`Actions for question: ${item.question}`}
                className={styles.iconButton}
                type="button"
              >
                <MoreHorizontal aria-hidden="true" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                onSelect={() => onDelete(item)}
                variant="destructive"
              >
                <Trash2 aria-hidden="true" />
                Delete history item
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <p className={styles.answer}>{item.answer}</p>
        <div className={styles.historyMetadata}>
          <span className={styles.citationBadge}>
            {item.citations.length} {item.citations.length === 1 ? "citation" : "citations"}
          </span>
          <time dateTime={item.created_at}>Asked {formatRelativeDate(item.created_at)}</time>
        </div>
      </article>
    </li>
  );
}

export function CollectionHistoryList({
  items,
  onDelete,
  onViewDetails,
}: {
  items: readonly QuestionHistoryItem[];
  onDelete: (item: QuestionHistoryItem) => void;
  onViewDetails: (item: QuestionHistoryItem) => void;
}) {
  return (
    <ul className={styles.historyList}>
      {items.map((item) => (
        <CollectionHistoryCard
          item={item}
          key={item.question_id}
          onDelete={onDelete}
          onViewDetails={onViewDetails}
        />
      ))}
    </ul>
  );
}
