"use client";

import { useEffect } from "react";
import type { LucideIcon } from "lucide-react";
import {
  CircleAlert,
  Clock3,
  FileText,
  Files,
  Folder,
  Folders,
  MessageCircleQuestion,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DocumentStatusBadge } from "@/features/collections/components/detail/collection-document-list";
import { DashboardPage } from "@/features/dashboard/components/dashboard-page";
import {
  DOCUMENT_FILE_TYPE_LABELS,
  isSupportedDocumentExtension,
} from "@/features/documents/file-validation";
import type { DocumentRecord } from "@/features/documents/types";
import type { QuestionHistoryItem } from "@/features/questions/questions-api-types";
import { useAuth } from "@/hooks/use-auth";
import { ApiError, getApiErrorMessage } from "@/lib/api";
import {
  formatDateTime,
  formatFileSize,
  formatRelativeDate,
} from "@/lib/formatters";
import { useOverview } from "../hooks/use-overview";
import type { OverviewCounts } from "../overview-api-types";
import styles from "./overview-screen.module.css";

const NUMBER_FORMATTER = new Intl.NumberFormat();

type MetricCardProps = {
  icon: LucideIcon;
  label: string;
  value: number;
};

function MetricCard({ icon: Icon, label, value }: MetricCardProps) {
  return (
    <article className={styles.metricCard}>
      <div>
        <p className={styles.metricLabel}>{label}</p>
        <p className={styles.metricValue}>{NUMBER_FORMATTER.format(value)}</p>
      </div>
      <span aria-hidden="true" className={styles.metricIcon}>
        <Icon />
      </span>
    </article>
  );
}

function OverviewMetrics({ counts }: { counts: OverviewCounts }) {
  return (
    <section aria-label="Workspace totals" className={styles.metrics}>
      <MetricCard
        icon={Files}
        label="Total Documents"
        value={counts.total_documents}
      />
      <MetricCard
        icon={MessageCircleQuestion}
        label="Total Questions"
        value={counts.total_questions}
      />
      <MetricCard
        icon={Folders}
        label="Total Collections"
        value={counts.total_collections}
      />
    </section>
  );
}

function documentType(document: DocumentRecord): string {
  const extension = document.original_extension.toLowerCase();
  return isSupportedDocumentExtension(extension)
    ? DOCUMENT_FILE_TYPE_LABELS[extension]
    : extension.replace(/^\./, "").toUpperCase();
}

function RecentDocuments({
  collectionNames,
  documents,
}: {
  collectionNames: ReadonlyMap<string, string>;
  documents: readonly DocumentRecord[];
}) {
  return (
    <section
      aria-labelledby="recent-documents-title"
      className={styles.sectionCard}
    >
      <header className={styles.sectionHeader}>
        <h2 id="recent-documents-title">Recent Documents</h2>
      </header>
      <Table className={styles.documentsTable}>
        <TableHeader className={styles.tableHeader}>
          <TableRow className={styles.tableRow}>
            <TableHead className={styles.filenameColumn}>Filename</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Size</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Date</TableHead>
            <TableHead>Collection</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {documents.length === 0 ? (
            <TableRow className={styles.tableRow}>
              <TableCell className={styles.tableEmpty} colSpan={6}>
                <FileText aria-hidden="true" />
                <span>No documents have been added yet.</span>
              </TableCell>
            </TableRow>
          ) : (
            documents.map((document) => (
              <TableRow className={styles.tableRow} key={document.id}>
                <TableCell className={styles.filenameCell}>
                  <span title={document.filename}>{document.filename}</span>
                </TableCell>
                <TableCell>{documentType(document)}</TableCell>
                <TableCell>{formatFileSize(document.size_bytes)}</TableCell>
                <TableCell>
                  <DocumentStatusBadge status={document.status} />
                </TableCell>
                <TableCell>
                  <time dateTime={document.created_at}>
                    {formatDateTime(document.created_at)}
                  </time>
                </TableCell>
                <TableCell>
                  {document.collection_id
                    ? (collectionNames.get(document.collection_id) ?? "—")
                    : "Unassigned"}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </section>
  );
}

function QuestionSource({ item }: { item: QuestionHistoryItem }) {
  const firstCitation = item.citations[0];
  if (!firstCitation) return null;

  return (
    <span className={styles.sourceChip}>
      <FileText aria-hidden="true" />
      <span title={firstCitation.document_filename}>
        {firstCitation.document_filename}
        {item.citations.length > 1
          ? ` +${item.citations.length - 1}`
          : ""}
      </span>
    </span>
  );
}

function QuestionCollection({
  collectionId,
  collectionNames,
}: {
  collectionId: string | null;
  collectionNames: ReadonlyMap<string, string>;
}) {
  const collectionName = collectionId
    ? collectionNames.get(collectionId)
    : undefined;
  const label = collectionId
    ? (collectionName ?? "Collection unavailable")
    : "No collection";

  return (
    <span
      aria-label={`Collection: ${label}`}
      className={styles.questionCollection}
    >
      <Folder aria-hidden="true" />
      <span title={collectionName}>{label}</span>
    </span>
  );
}

function RecentQuestions({
  collectionNames,
  questions,
}: {
  collectionNames: ReadonlyMap<string, string>;
  questions: readonly QuestionHistoryItem[];
}) {
  return (
    <section
      aria-labelledby="recent-questions-title"
      className={styles.sectionCard}
    >
      <header className={styles.sectionHeader}>
        <h2 id="recent-questions-title">Recent Questions</h2>
      </header>
      {questions.length === 0 ? (
        <div className={styles.questionEmpty}>
          <MessageCircleQuestion aria-hidden="true" />
          <span>No questions have been asked yet.</span>
        </div>
      ) : (
        <ul className={styles.questionList}>
          {questions.map((item) => (
            <li key={item.question_id}>
              <article className={styles.questionRow}>
                <span aria-hidden="true" className={styles.questionIcon}>
                  <MessageCircleQuestion />
                </span>
                <div className={styles.questionContent}>
                  <h3>{item.question}</h3>
                  <p>{item.answer}</p>
                  <div className={styles.questionMetadata}>
                    <time dateTime={item.created_at}>
                      <Clock3 aria-hidden="true" />
                      Asked {formatRelativeDate(item.created_at)}
                    </time>
                    <QuestionCollection
                      collectionId={item.collection_id}
                      collectionNames={collectionNames}
                    />
                    <QuestionSource item={item} />
                  </div>
                </div>
              </article>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function OverviewLoading() {
  return (
    <div
      aria-busy="true"
      aria-live="polite"
      className={styles.pageContent}
      role="status"
    >
      <span className={styles.srOnly}>Loading overview…</span>
      <div className={styles.metrics}>
        {[0, 1, 2].map((index) => (
          <div className={styles.metricCard} key={index}>
            <div className={styles.skeletonMetricText}>
              <Skeleton />
              <Skeleton />
            </div>
            <Skeleton className={styles.skeletonMetricIcon} />
          </div>
        ))}
      </div>
      <div className={styles.sectionCard}>
        <div className={styles.sectionHeader}>
          <Skeleton className={styles.skeletonSectionTitle} />
        </div>
        <div className={styles.skeletonRows}>
          {[0, 1, 2, 3, 4].map((index) => (
            <Skeleton key={index} />
          ))}
        </div>
      </div>
      <div className={styles.sectionCard}>
        <div className={styles.sectionHeader}>
          <Skeleton className={styles.skeletonSectionTitle} />
        </div>
        <div className={styles.skeletonQuestions}>
          {[0, 1, 2].map((index) => (
            <div key={index}>
              <Skeleton className={styles.skeletonQuestionIcon} />
              <div>
                <Skeleton />
                <Skeleton />
                <Skeleton />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function OverviewScreen() {
  const { logout } = useAuth();
  const request = useOverview();

  useEffect(() => {
    if (
      request.status === "error" &&
      request.error instanceof ApiError &&
      request.error.status === 401
    ) {
      logout();
    }
  }, [logout, request.error, request.status]);

  if (request.status === "loading") {
    return (
      <DashboardPage>
        <OverviewLoading />
      </DashboardPage>
    );
  }

  if (request.status === "error") {
    return (
      <DashboardPage>
        <section
          aria-labelledby="overview-error-title"
          className={styles.errorState}
          role="alert"
        >
          <CircleAlert aria-hidden="true" />
          <h2 id="overview-error-title">Overview couldn’t load</h2>
          <p>
            {getApiErrorMessage(
              request.error,
              "Your workspace summary is unavailable. Check your connection and try again.",
            )}
          </p>
          {request.error instanceof ApiError &&
          (request.error.status === 401 ||
            request.error.status === 403) ? null : (
            <Button
              onClick={() => void request.refetch().catch(() => undefined)}
              size="sm"
              type="button"
            >
              Try again
            </Button>
          )}
        </section>
      </DashboardPage>
    );
  }

  const collectionNames = new Map(
    request.data.collections.map(({ id, name }) => [id, name]),
  );

  return (
    <DashboardPage>
      <div className={styles.pageContent}>
        <OverviewMetrics counts={request.data.counts} />
        <RecentDocuments
          collectionNames={collectionNames}
          documents={request.data.recentDocuments}
        />
        <RecentQuestions
          collectionNames={collectionNames}
          questions={request.data.recentQuestions}
        />
      </div>
    </DashboardPage>
  );
}
