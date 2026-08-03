"use client";

import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from "react";
import { FileText, UploadCloud, X } from "lucide-react";
import type { DocumentUploadResponse } from "@/features/collections/collections-api-types";
import { formatFileSize } from "@/lib/formatters";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";
import { getUploadErrorMessage } from "@/features/documents/documents-error-utils";
import {
  createUploadQueue,
  DOCUMENT_UPLOAD_LIMITS,
  getUploadValidationMessage,
} from "@/features/documents/file-validation";
import { useUploadDocumentsMutation } from "@/features/documents/hooks/use-documents-api";
import { CollectionButton } from "../collection-button";
import {
  CollectionDialog,
  CollectionDialogCancel,
  CollectionDialogFooter,
} from "../dialogs/collection-dialog";
import styles from "./collection-detail.module.css";

function validateFiles(files: readonly File[]): string | undefined {
  if (!files.length) return "Choose at least one document.";
  return getUploadValidationMessage(createUploadQueue(files));
}

const MAX_UPLOAD_MB =
  DOCUMENT_UPLOAD_LIMITS.maxFileBytes / (1024 * 1024);

export function UploadCollectionDialog({
  collectionId,
  onClose,
  onUploadOutcomeUnknown,
  onUploaded,
}: {
  collectionId: string;
  onClose: () => void;
  onUploadOutcomeUnknown: () => void;
  onUploaded: (response: DocumentUploadResponse) => void;
}) {
  const { logout } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const chooseFilesRef = useRef<HTMLButtonElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [validationError, setValidationError] = useState<string>();
  const mutation = useUploadDocumentsMutation();

  const addFiles = (nextFiles: readonly File[]) => {
    if (mutation.isPending) return;
    const combined = [...files, ...nextFiles];
    const error = validateFiles(combined);
    setValidationError(error);
    setFiles(combined);
    mutation.reset();
  };

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    addFiles(Array.from(event.target.files ?? []));
    event.target.value = "";
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    addFiles(Array.from(event.dataTransfer.files));
  };

  const submit = () => {
    const error = validateFiles(files);
    setValidationError(error);
    if (error) return;
    void mutation
      .mutate({ collectionId, files })
      .then(onUploaded)
      .catch((uploadError: unknown) => {
        if (
          uploadError instanceof ApiError &&
          uploadError.code === "invalid_response"
        ) {
          onUploadOutcomeUnknown();
        }
      });
  };
  const confirmationUnknown =
    mutation.error instanceof ApiError &&
    mutation.error.code === "invalid_response";

  useEffect(() => {
    if (mutation.error instanceof ApiError && mutation.error.status === 401) {
      logout();
    }
  }, [logout, mutation.error]);

  return (
    <CollectionDialog
      description={`Upload one to ${DOCUMENT_UPLOAD_LIMITS.maxFiles} TXT, Markdown, or PDF documents directly to this collection.`}
      initialFocusRef={chooseFilesRef}
      onClose={mutation.isPending ? () => undefined : onClose}
      title="Upload to collection"
    >
      <div className={styles.uploadBody}>
        <div
          className={styles.dropzone}
          onDragOver={(event) => event.preventDefault()}
          onDrop={onDrop}
        >
          <UploadCloud aria-hidden="true" />
          <div>
            <strong>Drop documents here</strong>
            <p>
              TXT, MD, or PDF · up to {DOCUMENT_UPLOAD_LIMITS.maxFiles} files ·{" "}
              {MAX_UPLOAD_MB} MB each
            </p>
          </div>
          <CollectionButton
            disabled={
              mutation.isPending ||
              files.length >= DOCUMENT_UPLOAD_LIMITS.maxFiles
            }
            onClick={() => fileInputRef.current?.click()}
            ref={chooseFilesRef}
            tone="secondary"
            type="button"
          >
            Choose files
          </CollectionButton>
          <input
            accept=".txt,.md,.pdf,text/plain,text/markdown,application/pdf"
            aria-label="Choose documents"
            className="sr-only"
            disabled={mutation.isPending}
            multiple
            onChange={onFileChange}
            ref={fileInputRef}
            type="file"
          />
        </div>
        {files.length ? (
          <ul className={styles.uploadFileList}>
            {files.map((file, index) => (
              <li key={`${file.name}-${file.size}-${file.lastModified}-${index}`}>
                <FileText aria-hidden="true" />
                <div>
                  <strong>{file.name}</strong>
                  <span>{formatFileSize(file.size)}</span>
                </div>
                <button
                  aria-label={`Remove ${file.name}`}
                  disabled={mutation.isPending}
                  onClick={() => {
                    const next = files.filter(
                      (_candidate, candidateIndex) => candidateIndex !== index,
                    );
                    setFiles(next);
                    setValidationError(next.length ? validateFiles(next) : undefined);
                    mutation.reset();
                  }}
                  type="button"
                >
                  <X aria-hidden="true" />
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        {validationError || mutation.error ? (
          <p className={styles.dialogMutationError} role="alert">
            {validationError ?? getUploadErrorMessage(mutation.error)}
          </p>
        ) : null}
      </div>
      <CollectionDialogFooter>
        <CollectionDialogCancel disabled={mutation.isPending} />
        <CollectionButton
          disabled={
            mutation.isPending ||
            confirmationUnknown ||
            Boolean(validationError) ||
            files.length === 0
          }
          onClick={submit}
          type="button"
        >
          {mutation.isPending ? "Uploading…" : `Upload ${files.length || ""} ${files.length === 1 ? "document" : "documents"}`.trim()}
        </CollectionButton>
      </CollectionDialogFooter>
    </CollectionDialog>
  );
}
