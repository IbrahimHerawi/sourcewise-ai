"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DashboardPagination } from "@/features/dashboard/components/dashboard-pagination";
import { formatDateTime, formatFileSize } from "@/lib/formatters";
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
      <DashboardPagination
        ariaLabel="Documents pagination"
        currentPage={currentPage}
        onPageChange={onPageChange}
        pageCount={pageCount}
        pageSize={pageSize}
        total={total}
      />
    </>
  );
}
