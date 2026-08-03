import { FileText, Info, MoreHorizontal, Trash2 } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { CollectionDocument, DocumentStatus } from "@/features/collections/collections-api-types";
import { formatFileSize, formatRelativeDate } from "@/features/collections/collection-formatters";
import {
  DOCUMENT_STATUS_PRESENTATION,
  safeDocumentFailureMessage,
} from "@/features/documents/document-status";
import { cn } from "@/lib/utils";
import styles from "./collection-detail.module.css";

export function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  const presentation = DOCUMENT_STATUS_PRESENTATION[status];
  return (
    <span className={cn(styles.statusBadge, styles[`status-${presentation.tone}`])}>
      {presentation.label}
    </span>
  );
}

function DocumentOverflow({
  document,
  onDelete,
  onViewDetails,
}: {
  document: CollectionDocument;
  onDelete: (document: CollectionDocument) => void;
  onViewDetails: (document: CollectionDocument) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          aria-label={`Actions for ${document.filename}`}
          className={styles.iconButton}
          type="button"
        >
          <MoreHorizontal aria-hidden="true" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className={styles.documentMenu}>
        <DropdownMenuItem onSelect={() => onViewDetails(document)}>
          <Info aria-hidden="true" />
          View details
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={() => onDelete(document)}
          variant="destructive"
        >
          <Trash2 aria-hidden="true" />
          Delete document
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function CollectionDocumentRow({
  document,
  onDelete,
  onViewDetails,
}: {
  document: CollectionDocument;
  onDelete: (document: CollectionDocument) => void;
  onViewDetails: (document: CollectionDocument) => void;
}) {
  const status = DOCUMENT_STATUS_PRESENTATION[document.status];
  return (
    <li>
      <article className={styles.documentRow}>
        <FileText aria-hidden="true" className={styles.documentIcon} />
        <div className={styles.documentInformation}>
          <h3>{document.filename}</h3>
          <p>
            {document.original_extension.replace(/^\./, "").toUpperCase()} ·{" "}
            {formatFileSize(document.size_bytes)} · Updated {formatRelativeDate(document.updated_at)}
          </p>
          {document.status === "FAILED" ? (
            <p className={styles.documentFailure}>
              {safeDocumentFailureMessage(document.error_message)}
            </p>
          ) : status.processingMessage ? (
            <p>{status.processingMessage}</p>
          ) : null}
        </div>
        <DocumentStatusBadge status={document.status} />
        <DocumentOverflow
          document={document}
          onDelete={onDelete}
          onViewDetails={onViewDetails}
        />
      </article>
    </li>
  );
}

export function CollectionDocumentList({
  documents,
  onDelete,
  onViewDetails,
}: {
  documents: readonly CollectionDocument[];
  onDelete: (document: CollectionDocument) => void;
  onViewDetails: (document: CollectionDocument) => void;
}) {
  return (
    <ul className={styles.documentList}>
      {documents.map((document) => (
        <CollectionDocumentRow
          document={document}
          key={document.id}
          onDelete={onDelete}
          onViewDetails={onViewDetails}
        />
      ))}
    </ul>
  );
}
