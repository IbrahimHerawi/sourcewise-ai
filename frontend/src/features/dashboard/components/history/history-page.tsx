"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  ChevronDown,
  Clock3,
  FileText,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
} from "@/components/ui/pagination";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/hooks/use-auth";
import { useToast } from "@/hooks/use-toast";
import type {
  CitationResponse,
  DocumentSummaryResponse,
  PaginatedQuestionHistoryResponse,
  QuestionHistoryItemResponse,
} from "@/features/dashboard/history/types";
import {
  ApiError,
  api,
  getApiErrorMessage,
} from "@/lib/api";

import styles from "./history-page.module.css";

const PAGE_SIZE = 20;

function formatHistoryDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function getHistoryErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.status === 401) {
    return "Your session has expired. Sign in again to view history.";
  }
  if (error instanceof ApiError && error.status === 403) {
    return "You do not have permission to view history.";
  }
  return getApiErrorMessage(error, fallback);
}

function HistoryCitationList({ citations }: { citations: readonly CitationResponse[] }) {
  return (
    <ul className={styles.sourceList}>
      {citations.map((citation) => (
        <li className={styles.sourceItem} key={`${citation.chunk_id}-${citation.rank}`}>
          <div className={styles.sourceHeader}>
            <span className={styles.sourceRank}>{citation.rank}</span>
            <span className={styles.sourceName}>{citation.document_filename}</span>
          </div>
          <p className={styles.sourceExcerpt}>{citation.excerpt}</p>
          <span className={styles.sourceMetadata}>
            Chunk {citation.chunk_index + 1} · distance {citation.distance.toFixed(3)}
          </span>
        </li>
      ))}
    </ul>
  );
}

function HistoryEntryCard({ entry }: { entry: QuestionHistoryItemResponse }) {
  const [isAnswerExpanded, setIsAnswerExpanded] = useState(false);
  const [areSourcesExpanded, setAreSourcesExpanded] = useState(false);
  const canExpandAnswer = entry.answer.length > 420;
  const metadata = [entry.model, entry.provider].filter(
    (value): value is string => Boolean(value),
  );

  return (
    <li>
      <Card className={styles.card}>
        <CardContent className={styles.cardBody}>
          <h2 className={styles.question}>{entry.question}</h2>

          <div className={styles.answerGroup}>
            <p
              className={`${styles.answer} ${
                canExpandAnswer && !isAnswerExpanded ? styles.answerCollapsed : ""
              }`}
            >
              {entry.answer}
            </p>
            {canExpandAnswer ? (
              <Button
                aria-expanded={isAnswerExpanded}
                className={styles.showMore}
                onClick={() => setIsAnswerExpanded((expanded) => !expanded)}
                size="sm"
                type="button"
                variant="link"
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
                <span>{formatHistoryDate(entry.created_at)}</span>
              </span>
              {metadata.map((value) => (
                <span className={styles.metadataGroup} key={value}>
                  <span className={styles.metadataDivider} aria-hidden="true" />
                  <span className={styles.metadataItem}>{value}</span>
                </span>
              ))}
            </div>

            <Button
              aria-controls={`${entry.question_id}-sources`}
              aria-expanded={areSourcesExpanded}
              className={styles.sourceButton}
              disabled={entry.citations.length === 0}
              onClick={() => setAreSourcesExpanded((expanded) => !expanded)}
              size="sm"
              type="button"
              variant="ghost"
            >
              {entry.citations.length} {entry.citations.length === 1 ? "source" : "sources"}
              <ChevronDown
                className={`${styles.sourceIcon} ${areSourcesExpanded ? styles.sourceIconExpanded : ""}`}
                aria-hidden="true"
              />
            </Button>
          </div>

          {areSourcesExpanded ? (
            <div id={`${entry.question_id}-sources`}>
              <HistoryCitationList citations={entry.citations} />
            </div>
          ) : null}
        </CardContent>
      </Card>
    </li>
  );
}

function HistoryState({
  actionLabel,
  description,
  icon: Icon,
  onAction,
  title,
}: {
  actionLabel?: string;
  description: string;
  icon: typeof AlertCircle;
  onAction?: () => void;
  title: string;
}) {
  return (
    <div className={styles.stateCard} role="status">
      <Icon className={styles.stateIcon} aria-hidden="true" />
      <h2 className={styles.stateTitle}>{title}</h2>
      <p className={styles.stateDescription}>{description}</p>
      {onAction && actionLabel ? (
        <Button onClick={onAction} size="sm" type="button">
          {actionLabel}
        </Button>
      ) : null}
    </div>
  );
}

function HistorySkeleton() {
  return (
    <div className={styles.historyList} aria-label="Loading history" role="status">
      {Array.from({ length: 3 }, (_, index) => (
        <Card className={styles.card} key={index}>
          <CardContent className={styles.cardBody}>
            <Skeleton className={styles.questionSkeleton} />
            <Skeleton className={styles.answerSkeleton} />
            <Skeleton className={styles.answerSkeletonShort} />
            <Separator className={styles.separator} />
            <Skeleton className={styles.metadataSkeleton} />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export function HistoryPage() {
  const { logout } = useAuth();
  const { toast } = useToast();
  const [history, setHistory] = useState<PaginatedQuestionHistoryResponse | null>(null);
  const [documents, setDocuments] = useState<DocumentSummaryResponse[]>([]);
  const [selectedDocument, setSelectedDocument] = useState("all");
  const [page, setPage] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadErrorStatus, setLoadErrorStatus] = useState<number | null>(null);

  const loadHistory = useCallback(
    async () => {
      setIsLoading(true);
      setLoadError(null);
      setLoadErrorStatus(null);

      try {
        const response = await api.listQuestionHistory({
          limit: PAGE_SIZE,
          offset: page * PAGE_SIZE,
          documentId: selectedDocument === "all" ? undefined : selectedDocument,
        });

        if (response.items.length === 0 && response.total > 0 && page > 0) {
          setPage((currentPage) => currentPage - 1);
          return;
        }
        setHistory(response);
      } catch (error: unknown) {
        setLoadError(getHistoryErrorMessage(error, "Unable to load your history."));
        setLoadErrorStatus(error instanceof ApiError ? error.status : null);
      } finally {
        setIsLoading(false);
      }
    },
    [page, selectedDocument],
  );

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  useEffect(() => {
    let isMounted = true;

    async function loadDocuments() {
      try {
        const response = await api.listDocuments({ limit: 100 });
        if (isMounted) setDocuments(response.items);
      } catch (error: unknown) {
        if (isMounted) {
          toast({
            title: "Document filters unavailable",
            description: getHistoryErrorMessage(error, "History can still be viewed without filtering."),
            variant: "warning",
          });
        }
      }
    }

    void loadDocuments();
    return () => {
      isMounted = false;
    };
  }, [toast]);

  const documentNames = useMemo(
    () => new Map(documents.map((document) => [document.id, document.filename])),
    [documents],
  );
  const totalPages = history ? Math.max(1, Math.ceil(history.total / PAGE_SIZE)) : 1;
  const canGoPrevious = page > 0;
  const canGoNext = history ? (page + 1) * PAGE_SIZE < history.total : false;

  return (
    <section className={styles.page} aria-labelledby="history-heading">
      <div className={styles.content}>
        <header>
          <h1 className={styles.heading} id="history-heading">
            History
          </h1>
        </header>

        <div className={styles.toolbar}>
          {documents.length > 0 ? (
            <div className={styles.controlGroup}>
              <span className={styles.fieldLabel}>Filter by document</span>
              <Select
                value={selectedDocument}
                onValueChange={(value) => {
                  setSelectedDocument(value);
                  setPage(0);
                }}
              >
                <SelectTrigger className={styles.filter} aria-label="Filter history by document">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent align="end">
                  <SelectItem value="all">All documents</SelectItem>
                  {documents.map((document) => (
                    <SelectItem key={document.id} value={document.id}>
                      {document.filename}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}
        </div>

        {isLoading ? <HistorySkeleton /> : null}

        {!isLoading && loadError ? (
          <HistoryState
            actionLabel={loadErrorStatus === 401 ? "Sign in again" : "Try again"}
            description={loadError}
            icon={AlertCircle}
            onAction={loadErrorStatus === 401 ? logout : () => void loadHistory()}
            title="History could not be loaded"
          />
        ) : null}

        {!isLoading && !loadError && history?.total === 0 ? (
          <HistoryState
            description={
              selectedDocument === "all"
                ? "Questions you ask will appear here after they are answered."
                : `No history is associated with ${documentNames.get(selectedDocument) ?? "this document"}.`
            }
            icon={FileText}
            title="No history found"
          />
        ) : null}

        {!isLoading && !loadError && history && history.items.length > 0 ? (
          <>
            <ol className={styles.historyList} aria-label="Question history">
              {history.items.map((entry) => (
                <HistoryEntryCard entry={entry} key={entry.question_id} />
              ))}
            </ol>

            <div className={styles.tableFooter}>
              <p className={styles.resultCount}>
                Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, history.total)} of {history.total}
              </p>
              <Pagination className={styles.pagination}>
                <PaginationContent className={styles.paginationContent}>
                  <PaginationItem>
                    <Button
                      className={styles.paginationButton}
                      disabled={!canGoPrevious}
                      onClick={() => setPage((currentPage) => Math.max(0, currentPage - 1))}
                      size="default"
                      type="button"
                      variant="outline"
                    >
                      Previous
                    </Button>
                  </PaginationItem>
                  <PaginationItem>
                    <Button
                      className={styles.paginationButton}
                      disabled={!canGoNext}
                      onClick={() => setPage((currentPage) => currentPage + 1)}
                      size="default"
                      type="button"
                    >
                      Next
                    </Button>
                  </PaginationItem>
                </PaginationContent>
              </Pagination>
            </div>
            <span className={styles.visuallyHidden}>Page {page + 1} of {totalPages}</span>
          </>
        ) : null}
      </div>
    </section>
  );
}
