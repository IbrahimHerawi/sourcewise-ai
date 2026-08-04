"use client";

import { useEffect, useRef } from "react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { CollectionButton } from "@/features/collections/components/collection-button";
import { formatDateTime, formatFileSize } from "@/lib/formatters";
import { DocumentStatusBadge } from "@/features/collections/components/detail/collection-document-list";
import {
  CollectionDialog,
  CollectionDialogCancel,
  CollectionDialogFooter,
} from "@/features/collections/components/dialogs/collection-dialog";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";
import {
  DOCUMENT_STATUS_PRESENTATION,
  safeDocumentFailureMessage,
} from "../document-status";
import { getDeleteErrorMessage } from "../documents-error-utils";
import { useDeleteDocumentMutation } from "../hooks/use-documents-api";
import type { DocumentRecord } from "../types";
import styles from "./documents-page.module.css";

export function DocumentDetailsPanel({
  document,
  onClose,
}: {
  document: DocumentRecord;
  onClose: () => void;
}) {
  const status = DOCUMENT_STATUS_PRESENTATION[document.status];
  const rows = [
    ["Document ID", document.id],
    ["Collection ID", document.collection_id ?? "Not assigned"],
    ["Filename", document.filename],
    ["Extension", document.original_extension],
    ["MIME type", document.content_type],
    ["File size", formatFileSize(document.size_bytes)],
    ["Created", formatDateTime(document.created_at)],
    ["Updated", formatDateTime(document.updated_at)],
  ] as const;

  return (
    <Sheet open onOpenChange={(open) => !open && onClose()}>
      <SheetContent className={styles.detailsPanel} side="right">
        <SheetHeader className={styles.detailsHeader}>
          <SheetTitle>Document metadata</SheetTitle>
          <SheetDescription>
            Metadata recorded for this uploaded document.
          </SheetDescription>
        </SheetHeader>
        <div className={styles.detailsStatus}>
          <span>Status</span>
          <DocumentStatusBadge status={document.status} />
        </div>
        <dl className={styles.metadataList}>
          {rows.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
        {document.status === "FAILED" ? (
          <div className={styles.detailsFailure} role="status">
            <strong>Processing failed</strong>
            <p>{safeDocumentFailureMessage(document.error_message)}</p>
          </div>
        ) : status.processingMessage ? (
          <p className={styles.detailsProcessing} role="status">
            {status.processingMessage}
          </p>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}

export function DeleteDocumentDialog({
  document,
  onClose,
  onDeleted,
}: {
  document: DocumentRecord;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const { logout } = useAuth();
  const cancelRef = useRef<HTMLButtonElement>(null);
  const mutation = useDeleteDocumentMutation();
  const description = `Delete ${document.filename}? This permanently removes it from the library and future answers. Citations already saved in question history remain available.`;
  const submit = () => {
    void mutation
      .mutate(document.id)
      .then(onDeleted)
      .catch(() => undefined);
  };

  useEffect(() => {
    if (mutation.error instanceof ApiError && mutation.error.status === 401) {
      logout();
    }
  }, [logout, mutation.error]);

  return (
    <CollectionDialog
      description={description}
      descriptionVariant="body"
      initialFocusRef={cancelRef}
      onClose={mutation.isPending ? () => undefined : onClose}
      role="alertdialog"
      title="Delete document?"
    >
      <CollectionDialogFooter>
        <CollectionDialogCancel disabled={mutation.isPending} ref={cancelRef}>
          Cancel
        </CollectionDialogCancel>
        <CollectionButton
          disabled={mutation.isPending}
          onClick={submit}
          tone="solid-danger"
          type="button"
        >
          {mutation.isPending ? "Deleting…" : "Delete document"}
        </CollectionButton>
      </CollectionDialogFooter>
      {mutation.error ? (
        <p className={styles.dialogError} role="alert">
          {getDeleteErrorMessage(mutation.error)}
        </p>
      ) : null}
    </CollectionDialog>
  );
}
