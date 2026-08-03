"use client";

import { useEffect, useRef } from "react";
import { CircleAlert, Loader2 } from "lucide-react";
import type { CollectionDocument } from "@/features/collections/collections-api-types";
import { formatDateTime, formatFileSize } from "@/features/collections/collection-formatters";
import { safeDocumentFailureMessage } from "@/features/documents/document-status";
import {
  useDeleteDocumentMutation,
  useDocumentDetails,
} from "@/features/documents/hooks/use-documents-api";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";
import {
  getDeleteErrorMessage,
  getDocumentDetailsErrorMessage,
} from "@/features/documents/documents-error-utils";
import { CollectionButton } from "../collection-button";
import {
  CollectionDialog,
  CollectionDialogCancel,
  CollectionDialogFooter,
} from "../dialogs/collection-dialog";
import { DocumentStatusBadge } from "./collection-document-list";
import styles from "./collection-detail.module.css";

export function DocumentDetailsDialog({
  documentId,
  onClose,
}: {
  documentId: string;
  onClose: () => void;
}) {
  const { logout } = useAuth();
  const closeRef = useRef<HTMLButtonElement>(null);
  const state = useDocumentDetails(documentId);

  useEffect(() => {
    if (state.status === "error" && state.error instanceof ApiError) {
      if (state.error.status === 401) logout();
    }
  }, [logout, state.error, state.status]);

  return (
    <CollectionDialog
      description="Metadata for this uploaded document."
      initialFocusRef={closeRef}
      onClose={onClose}
      title="Document details"
    >
      {state.status === "loading" ? (
        <div aria-busy="true" className={styles.dialogLoading}>
          <Loader2 aria-hidden="true" />
          <span>Loading document details…</span>
        </div>
      ) : state.status === "error" ? (
        <div className={styles.dialogError} role="alert">
          <CircleAlert aria-hidden="true" />
          <p>{getDocumentDetailsErrorMessage(state.error)}</p>
          <CollectionButton onClick={() => void state.refetch().catch(() => undefined)}>
            Try again
          </CollectionButton>
        </div>
      ) : (
        <DocumentMetadata document={state.data} />
      )}
      <CollectionDialogFooter>
        <CollectionDialogCancel ref={closeRef}>Close</CollectionDialogCancel>
      </CollectionDialogFooter>
    </CollectionDialog>
  );
}

function DocumentMetadata({ document }: { document: CollectionDocument }) {
  const rows = [
    ["Filename", document.filename],
    ["Extension", document.original_extension],
    ["MIME type", document.content_type],
    ["File size", formatFileSize(document.size_bytes)],
    ["Created", formatDateTime(document.created_at)],
    ["Updated", formatDateTime(document.updated_at)],
  ];

  return (
    <div className={styles.documentDetailsBody}>
      <div className={styles.documentDetailsStatus}>
        <span>Status</span>
        <DocumentStatusBadge status={document.status} />
      </div>
      <dl className={styles.detailsList}>
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      {document.status === "FAILED" ? (
        <div className={styles.failureCallout} role="status">
          <strong>Processing failed</strong>
          <p>{safeDocumentFailureMessage(document.error_message)}</p>
        </div>
      ) : null}
    </div>
  );
}

export function DeleteDocumentDialog({
  document,
  onClose,
  onDeleted,
}: {
  document: CollectionDocument;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const { logout } = useAuth();
  const cancelRef = useRef<HTMLButtonElement>(null);
  const mutation = useDeleteDocumentMutation();
  const submit = () => {
    void mutation.mutate(document.id).then(onDeleted).catch(() => undefined);
  };

  useEffect(() => {
    if (mutation.error instanceof ApiError && mutation.error.status === 401) {
      logout();
    }
  }, [logout, mutation.error]);

  return (
    <CollectionDialog
      description={`Delete ${document.filename} permanently? This removes the uploaded document and its processed data. Existing citation snapshots remain in question history.`}
      descriptionVariant="warning"
      initialFocusRef={cancelRef}
      onClose={mutation.isPending ? () => undefined : onClose}
      role="alertdialog"
      title="Delete document?"
    >
      <CollectionDialogFooter>
        <CollectionDialogCancel disabled={mutation.isPending} ref={cancelRef} />
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
        <p className={styles.dialogMutationError} role="alert">
          {getDeleteErrorMessage(mutation.error)}
        </p>
      ) : null}
    </CollectionDialog>
  );
}
