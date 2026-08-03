"use client";

import { ChevronLeft, ChevronRight, MoreHorizontal } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatDateTime, formatFileSize } from "@/lib/formatters";
import { getPaginationItems } from "@/features/collections/collection-detail-utils";
import { DocumentStatusBadge } from "@/features/collections/components/detail/collection-document-list";
import {
  DOCUMENT_STATUS_PRESENTATION,
  safeDocumentFailureMessage,
} from "@/features/documents/document-status";
import type { DocumentCollection, DocumentRecord } from "../types";
import styles from "./documents-page.module.css";

type DocumentLibraryProps = {
  collections: readonly DocumentCollection[];
  currentPage: number;
  documents: readonly DocumentRecord[];
  filter: string;
  onDelete: (document: DocumentRecord, opener: HTMLButtonElement) => void;
  onFilterChange: (filter: string) => void;
  onOpenDetails: (document: DocumentRecord, opener: HTMLButtonElement) => void;
  onPageChange: (page: number) => void;
  pageCount: number;
  pageSize: number;
  total: number;
};

function ExtensionBadge({ extension }: { extension: string }) {
  const normalized = extension.replace(/^\./, "").toLowerCase();
  return (
    <span className={`${styles.extensionBadge} ${styles[`extension-${normalized}`] ?? ""}`}>
      .{normalized.toUpperCase()}
    </span>
  );
}

function DocumentRow({
  document,
  onDelete,
  onOpenDetails,
}: Pick<DocumentLibraryProps, "onDelete" | "onOpenDetails"> & {
  document: DocumentRecord;
}) {
  const status = DOCUMENT_STATUS_PRESENTATION[document.status];
  return (
    <li>
      <article className={styles.documentRow}>
        <ExtensionBadge extension={document.original_extension} />
        <div className={styles.documentIdentity}>
          <h3 title={document.filename}>{document.filename}</h3>
          {document.status === "FAILED" ? (
            <p>{safeDocumentFailureMessage(document.error_message)}</p>
          ) : status.processingMessage ? (
            <p className={styles.documentProcessingMessage}>
              {status.processingMessage}
            </p>
          ) : null}
        </div>
        <p className={styles.documentMetadata}>
          {formatFileSize(document.size_bytes)}
          <span aria-hidden="true"> · </span>
          {formatDateTime(document.created_at)}
        </p>
        <DocumentStatusBadge status={document.status} />
        <div className={styles.documentActions}>
          {status.actions.includes("details") ? (
            <button
              onClick={(event) => onOpenDetails(document, event.currentTarget)}
              type="button"
            >
              Details
            </button>
          ) : null}
          {status.actions.includes("details") &&
          status.actions.includes("delete") ? (
            <span aria-hidden="true">·</span>
          ) : null}
          {status.actions.includes("delete") ? (
            <button
              onClick={(event) => onDelete(document, event.currentTarget)}
              type="button"
            >
              Delete
            </button>
          ) : null}
        </div>
      </article>
    </li>
  );
}

function DocumentsPagination({
  currentPage,
  onPageChange,
  pageCount,
  pageSize,
  total,
}: Pick<
  DocumentLibraryProps,
  "currentPage" | "onPageChange" | "pageCount" | "pageSize" | "total"
>) {
  const first = total === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const last = Math.min(currentPage * pageSize, total);

  return (
    <div className={styles.paginationBar}>
      <p>Showing {first}–{last} of {total}</p>
      <nav aria-label="Documents pagination" className={styles.paginationControls}>
        <button
          aria-label="Go to previous page"
          className={styles.paginationDirection}
          disabled={currentPage === 1}
          onClick={() => onPageChange(currentPage - 1)}
          type="button"
        >
          <ChevronLeft aria-hidden="true" />
          <span>Previous</span>
        </button>
        <ol>
          {getPaginationItems(currentPage, pageCount).map((item, index) =>
            item === "ellipsis" ? (
              <li className={styles.paginationEllipsis} key={`ellipsis-${index}`}>
                <MoreHorizontal aria-hidden="true" />
                <span className="sr-only">More pages</span>
              </li>
            ) : (
              <li key={item}>
                <button
                  aria-current={item === currentPage ? "page" : undefined}
                  aria-label={`Go to page ${item}`}
                  className={styles.paginationPage}
                  onClick={() => onPageChange(item)}
                  type="button"
                >
                  {item}
                </button>
              </li>
            ),
          )}
        </ol>
        <button
          aria-label="Go to next page"
          className={styles.paginationDirection}
          disabled={currentPage === pageCount}
          onClick={() => onPageChange(currentPage + 1)}
          type="button"
        >
          <span>Next</span>
          <ChevronRight aria-hidden="true" />
        </button>
      </nav>
    </div>
  );
}

export function DocumentsToolbar({
  collections,
  filter,
  onFilterChange,
  showFilter = true,
}: Pick<DocumentLibraryProps, "collections" | "filter" | "onFilterChange"> & {
  showFilter?: boolean;
}) {
  return (
    <div className={styles.libraryToolbar}>
      <h2 className={styles.libraryTitle}>All documents</h2>
      {showFilter ? (
        <div className={styles.collectionFilter}>
          <label htmlFor="documents-collection-filter">Collection</label>
          <Select onValueChange={onFilterChange} value={filter}>
            <SelectTrigger
              aria-label="Filter documents by collection"
              className={styles.collectionSelect}
              id="documents-collection-filter"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent className={styles.collectionSelectContent}>
              <SelectItem value="all">All documents</SelectItem>
              {collections.map((collection) => (
                <SelectItem key={collection.id} value={collection.id}>
                  {collection.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : null}
    </div>
  );
}

export function DocumentList({
  currentPage,
  documents,
  onDelete,
  onOpenDetails,
  onPageChange,
  pageCount,
  pageSize,
  total,
}: Omit<DocumentLibraryProps, "collections" | "filter" | "onFilterChange">) {
  return (
    <>
      <ul className={styles.documentSurface}>
        {documents.map((document) => (
          <DocumentRow
            document={document}
            key={document.id}
            onDelete={onDelete}
            onOpenDetails={onOpenDetails}
          />
        ))}
      </ul>
      <DocumentsPagination
        currentPage={currentPage}
        onPageChange={onPageChange}
        pageCount={pageCount}
        pageSize={pageSize}
        total={total}
      />
    </>
  );
}
