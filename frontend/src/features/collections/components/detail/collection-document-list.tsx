import { FileText, MoreHorizontal, Trash2 } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type {
  CollectionDocument,
  DocumentStatus,
} from "@/features/collections/collection-detail-types";
import { cn } from "@/lib/utils";
import styles from "./collection-detail.module.css";

const statusLabels = {
  ready: "Ready",
  processing: "Processing",
  pending: "Pending",
} as const satisfies Record<DocumentStatus, string>;

export function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <span className={cn(styles.statusBadge, styles[`status-${status}`])}>
      {statusLabels[status]}
    </span>
  );
}

function DocumentOverflow({ documentName }: { documentName: string }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          aria-label={`Actions for ${documentName}`}
          className={styles.iconButton}
          type="button"
        >
          <MoreHorizontal aria-hidden="true" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className={styles.documentMenu}>
        <DropdownMenuItem>View details</DropdownMenuItem>
        <DropdownMenuItem variant="destructive">
          <Trash2 aria-hidden="true" />
          Remove from collection
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function CollectionDocumentRow({
  document,
}: {
  document: CollectionDocument;
}) {
  const isQueued = document.status !== "ready";

  return (
    <li>
      <article className={cn(styles.documentRow, isQueued && styles.queuedRow)}>
        <FileText aria-hidden="true" className={styles.documentIcon} />
        <div className={styles.documentInformation}>
          <h3 className={cn(isQueued && styles.queuedDocumentName)}>
            {document.name}
          </h3>
          <p>{document.metadata}</p>
          {document.status === "processing" && document.progress !== undefined ? (
            <div
              aria-label={`${document.progress}% processed`}
              aria-valuemax={100}
              aria-valuemin={0}
              aria-valuenow={document.progress}
              className={styles.progressTrack}
              role="progressbar"
            >
              <span style={{ width: `${document.progress}%` }} />
            </div>
          ) : null}
        </div>
        <DocumentStatusBadge status={document.status} />
        <DocumentOverflow documentName={document.name} />
      </article>
    </li>
  );
}

export function CollectionDocumentList({
  documents,
}: {
  documents: readonly CollectionDocument[];
}) {
  return (
    <ul className={styles.documentList}>
      {documents.map((document) => (
        <CollectionDocumentRow document={document} key={document.id} />
      ))}
    </ul>
  );
}
