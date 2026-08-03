import { MoreHorizontal, Trash2 } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { formatRelativeDate } from "@/lib/formatters";
import type { QuestionHistoryItem } from "../questions-api-types";
import styles from "./question-history-list.module.css";

export function QuestionHistoryCard({
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
      <article className={styles.card}>
        <div className={styles.header}>
          <button
            className={styles.titleButton}
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
        <div className={styles.metadata}>
          <span className={styles.citationBadge}>
            {item.citations.length}{" "}
            {item.citations.length === 1 ? "citation" : "citations"}
          </span>
          <time dateTime={item.created_at}>
            Asked {formatRelativeDate(item.created_at)}
          </time>
        </div>
      </article>
    </li>
  );
}

export function QuestionHistoryList({
  items,
  onDelete,
  onViewDetails,
}: {
  items: readonly QuestionHistoryItem[];
  onDelete: (item: QuestionHistoryItem) => void;
  onViewDetails: (item: QuestionHistoryItem) => void;
}) {
  return (
    <ul className={styles.list}>
      {items.map((item) => (
        <QuestionHistoryCard
          item={item}
          key={item.question_id}
          onDelete={onDelete}
          onViewDetails={onViewDetails}
        />
      ))}
    </ul>
  );
}
