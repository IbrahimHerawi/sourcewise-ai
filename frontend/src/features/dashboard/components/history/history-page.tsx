"use client";

import { useMemo, useState } from "react";
import { ChevronDown, Clock3 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  historyDocumentFilters,
  historyEntries,
  historyTotalCount,
} from "@/features/dashboard/history/mock-data";
import type { HistoryEntry } from "@/features/dashboard/history/types";

import styles from "./history-page.module.css";

type HistoryEntryCardProps = {
  entry: HistoryEntry;
};

function HistoryEntryCard({ entry }: HistoryEntryCardProps) {
  const [isAnswerExpanded, setIsAnswerExpanded] = useState(false);
  const [areSourcesExpanded, setAreSourcesExpanded] = useState(false);

  return (
    <li>
      <Card className={styles.card}>
        <CardContent className={styles.cardBody}>
          <h2 className={styles.question}>{entry.question}</h2>

          <div className={styles.answerGroup}>
            <p
              className={`${styles.answer} ${
                entry.isExpandable && !isAnswerExpanded
                  ? styles.answerCollapsed
                  : ""
              }`}
            >
              {entry.answer}
            </p>

            {entry.isExpandable ? (
              <Button
                className={styles.showMore}
                onClick={() => setIsAnswerExpanded((expanded) => !expanded)}
                variant="link"
                size="sm"
                type="button"
                aria-expanded={isAnswerExpanded}
              >
                {isAnswerExpanded ? "Show less" : "Show more"}
              </Button>
            ) : null}
          </div>

          <Separator className={styles.separator} />

          <div className={styles.metadata}>
            <div className={styles.metadataDetails}>
              <span className={styles.metadataItem}>
                <Clock3 className={styles.metadataIcon} aria-hidden="true" />
                <span>{entry.createdAt}</span>
              </span>
              <span className={styles.metadataDivider} aria-hidden="true" />
              <span className={styles.metadataItem}>{entry.model}</span>
              <span className={styles.metadataDivider} aria-hidden="true" />
              <span className={styles.metadataItem}>{entry.provider}</span>
            </div>

            <Button
              className={styles.sourceButton}
              onClick={() => setAreSourcesExpanded((expanded) => !expanded)}
              variant="ghost"
              size="sm"
              type="button"
              aria-expanded={areSourcesExpanded}
              aria-controls={`${entry.id}-sources`}
            >
              <span>
                {entry.sourceCount} {entry.sourceCount === 1 ? "source" : "sources"}
              </span>
              <ChevronDown
                className={`${styles.sourceIcon} ${
                  areSourcesExpanded ? styles.sourceIconExpanded : ""
                }`}
                aria-hidden="true"
              />
            </Button>
          </div>

          {areSourcesExpanded ? (
            <ul className={styles.sourceList} id={`${entry.id}-sources`}>
              {entry.sources.map((source) => (
                <li key={source}>{source}</li>
              ))}
            </ul>
          ) : null}
        </CardContent>
      </Card>
    </li>
  );
}

function HistoryEmptyState() {
  return (
    <div className={styles.emptyState} role="status">
      <p className={styles.emptyStateTitle}>No history found</p>
      <p className={styles.emptyStateDescription}>
        There are no questions for the selected document yet.
      </p>
    </div>
  );
}

export function HistoryPage() {
  const [selectedDocument, setSelectedDocument] = useState("all");

  const visibleEntries = useMemo(
    () =>
      selectedDocument === "all"
        ? historyEntries
        : historyEntries.filter((entry) => entry.documentId === selectedDocument),
    [selectedDocument],
  );

  const visibleCount = visibleEntries.length;
  const totalCount = selectedDocument === "all" ? historyTotalCount : visibleCount;
  const displayedEnd =
    selectedDocument === "all"
      ? Math.min(20, historyTotalCount)
      : visibleCount;

  return (
    <section className={styles.page} aria-labelledby="history-heading">
      <div className={styles.content}>
        <h1 className={styles.visuallyHidden} id="history-heading">
          History
        </h1>

        <div className={styles.toolbar}>
          <Select value={selectedDocument} onValueChange={setSelectedDocument}>
            <SelectTrigger className={styles.filter} aria-label="Filter history by document">
              <SelectValue />
            </SelectTrigger>
            <SelectContent align="end">
              {historyDocumentFilters.map((filter) => (
                <SelectItem key={filter.id} value={filter.id}>
                  {filter.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {visibleEntries.length > 0 ? (
          <ol className={styles.historyList} aria-label="Question history">
            {visibleEntries.map((entry) => (
              <HistoryEntryCard entry={entry} key={entry.id} />
            ))}
          </ol>
        ) : (
          <HistoryEmptyState />
        )}

        <p className={styles.resultCount}>
          Showing {visibleCount > 0 ? `1-${displayedEnd}` : "0"} of {totalCount}
        </p>
      </div>
    </section>
  );
}
