import type { ReactNode } from "react";
import { Folder, MoreHorizontal, Trash2 } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { formatRelativeDate } from "@/lib/formatters";
import type { QuestionHistoryItem } from "../questions-api-types";
import styles from "./question-history-list.module.css";

export function QuestionHistoryMetadataChip({
  children,
  tone = "source",
}: {
  children: ReactNode;
  tone?: "collection" | "source";
}) {
  return (
    <span
      className={`${styles.metadataChip} ${
        tone === "collection" ? styles.collectionChip : styles.sourceChip
      }`}
    >
      {children}
    </span>
  );
}

export function QuestionHistoryCard({
  collectionName,
  item,
  onDelete,
  onViewDetails,
}: {
  collectionName?: string;
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
          <QuestionHistoryMetadataChip>
            {item.citations.length}{" "}
            {item.citations.length === 1 ? "source" : "sources"}
          </QuestionHistoryMetadataChip>
          {collectionName ? (
            <QuestionHistoryMetadataChip tone="collection">
              <Folder aria-hidden="true" />
              <span className={styles.collectionName} title={collectionName}>
                {collectionName}
              </span>
            </QuestionHistoryMetadataChip>
          ) : null}
          <time dateTime={item.created_at}>
            Asked {formatRelativeDate(item.created_at)}
          </time>
        </div>
      </article>
    </li>
  );
}

export function QuestionHistoryList({
  collectionNames,
  items,
  onDelete,
  onViewDetails,
}: {
  collectionNames?: ReadonlyMap<string, string>;
  items: readonly QuestionHistoryItem[];
  onDelete: (item: QuestionHistoryItem) => void;
  onViewDetails: (item: QuestionHistoryItem) => void;
}) {
  return (
    <ul className={styles.list}>
      {items.map((item) => (
        <QuestionHistoryCard
          collectionName={
            item.collection_id
              ? collectionNames?.get(item.collection_id)
              : undefined
          }
          item={item}
          key={item.question_id}
          onDelete={onDelete}
          onViewDetails={onViewDetails}
        />
      ))}
    </ul>
  );
}
