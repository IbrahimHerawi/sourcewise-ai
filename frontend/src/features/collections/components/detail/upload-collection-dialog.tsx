"use client";

import { useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { FileText, UploadCloud, X } from "lucide-react";
import { uploadCollectionDocuments } from "@/features/collections/collections-api";
import type { DocumentUploadResponse } from "@/features/collections/collections-api-types";
import { formatFileSize } from "@/features/collections/collection-formatters";
import { useApiMutation } from "@/hooks/use-api-request";
import { getApiErrorMessage } from "@/lib/api";
import { CollectionButton } from "../collection-button";
import {
  CollectionDialog,
  CollectionDialogCancel,
  CollectionDialogFooter,
} from "../dialogs/collection-dialog";
import styles from "./collection-detail.module.css";

const ACCEPTED_EXTENSIONS = [".txt", ".md", ".pdf"];
const MAX_FILES = 3;
const MAX_FILE_BYTES = 10 * 1024 * 1024;

function validateFiles(files: readonly File[]): string | undefined {
  if (!files.length) return "Choose at least one document.";
  if (files.length > MAX_FILES) return "Choose no more than three documents.";
  const unsupported = files.find(
    (file) => !ACCEPTED_EXTENSIONS.some((extension) => file.name.toLowerCase().endsWith(extension)),
  );
  if (unsupported) return `${unsupported.name} is not a supported file type.`;
  const oversized = files.find((file) => file.size > MAX_FILE_BYTES);
  if (oversized) return `${oversized.name} is larger than the 10 MB limit.`;
  return undefined;
}

export function UploadCollectionDialog({
  collectionId,
  onClose,
  onUploaded,
}: {
  collectionId: string;
  onClose: () => void;
  onUploaded: (response: DocumentUploadResponse) => void;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const chooseFilesRef = useRef<HTMLButtonElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [validationError, setValidationError] = useState<string>();
  const mutation = useApiMutation((selectedFiles: readonly File[], signal) =>
    uploadCollectionDocuments(collectionId, selectedFiles, signal),
  );

  const addFiles = (nextFiles: readonly File[]) => {
    if (mutation.isPending) return;
    const unique = [...files];
    nextFiles.forEach((file) => {
      if (!unique.some((candidate) => candidate.name === file.name && candidate.size === file.size)) {
        unique.push(file);
      }
    });
    const error = validateFiles(unique);
    setValidationError(error);
    if (unique.length <= MAX_FILES) setFiles(unique);
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
    void mutation.mutate(files).then(onUploaded).catch(() => undefined);
  };

  return (
    <CollectionDialog
      description="Upload one to three TXT, Markdown, or PDF documents directly to this collection."
      initialFocusRef={chooseFilesRef}
      onClose={onClose}
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
            <p>TXT, MD, or PDF · up to 3 files · 10 MB each</p>
          </div>
          <CollectionButton
            disabled={mutation.isPending || files.length >= MAX_FILES}
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
            {files.map((file) => (
              <li key={`${file.name}-${file.size}`}>
                <FileText aria-hidden="true" />
                <div>
                  <strong>{file.name}</strong>
                  <span>{formatFileSize(file.size)}</span>
                </div>
                <button
                  aria-label={`Remove ${file.name}`}
                  disabled={mutation.isPending}
                  onClick={() => {
                    const next = files.filter((candidate) => candidate !== file);
                    setFiles(next);
                    setValidationError(next.length ? validateFiles(next) : undefined);
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
            {validationError ?? getApiErrorMessage(mutation.error, "The documents could not be uploaded.")}
          </p>
        ) : null}
      </div>
      <CollectionDialogFooter>
        <CollectionDialogCancel disabled={mutation.isPending} />
        <CollectionButton
          disabled={mutation.isPending || files.length === 0}
          onClick={submit}
          type="button"
        >
          {mutation.isPending ? "Uploading…" : `Upload ${files.length || ""} ${files.length === 1 ? "document" : "documents"}`.trim()}
        </CollectionButton>
      </CollectionDialogFooter>
    </CollectionDialog>
  );
}
