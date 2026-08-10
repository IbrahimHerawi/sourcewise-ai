"use client";

import {
  useState,
  type ChangeEvent,
  type DragEvent,
  type RefObject,
} from "react";
import { CheckCircle2, CircleAlert, FileText, FileUp, X } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CollectionButton } from "@/features/collections/components/collection-button";
import { formatFileSize } from "@/lib/formatters";
import {
  DOCUMENT_UPLOAD_LIMITS,
  getUploadValidationMessage,
  hasBlockingUploadError,
} from "../file-validation";
import type { DocumentCollection, UploadQueueItem } from "../types";
import styles from "./documents-page.module.css";

type DocumentUploadCardProps = {
  collectionError?: string;
  collectionOptions: readonly DocumentCollection[];
  collectionsUnavailable: boolean;
  fileInputRef: RefObject<HTMLInputElement | null>;
  isUploading: boolean;
  onCollectionChange: (collectionId: string | null) => void;
  onFilesSelected: (files: readonly File[]) => void;
  onRemove: (id: string) => void;
  onUpload: () => void;
  queue: readonly UploadQueueItem[];
  selectedCollectionId: string | null;
  serverError?: string;
  submissionBlocked?: boolean;
  successMessage?: string;
};

const QUEUE_STATUS_LABELS = {
  valid: "Ready to upload",
  "empty-file": "Empty file",
  "invalid-type": "Unsupported type",
  "too-large": `Over ${
    DOCUMENT_UPLOAD_LIMITS.maxFileBytes / (1024 * 1024)
  } MB`,
  "too-many-files": "Over batch limit",
} as const;

function UploadQueue({
  isUploading,
  onRemove,
  queue,
}: Pick<DocumentUploadCardProps, "isUploading" | "onRemove" | "queue">) {
  if (queue.length === 0) return <div aria-hidden="true" className={styles.emptyQueue} />;

  return (
    <ul aria-label="Selected files" className={styles.uploadQueue}>
      {queue.map((item) => {
        const invalid = item.status !== "valid";
        return (
          <li
            className={invalid ? styles.invalidQueueItem : undefined}
            key={item.id}
          >
            <FileText aria-hidden="true" className={styles.queueFileIcon} />
            <div className={styles.queueFileInformation}>
              <p>
                <strong>{item.file.name}</strong>
                <span aria-hidden="true"> · </span>
                <span>{formatFileSize(item.file.size)}</span>
              </p>
              {item.message ? <span>{item.message}</span> : null}
            </div>
            <span className={invalid ? styles.queueStatusError : styles.queueStatusReady}>
              {QUEUE_STATUS_LABELS[item.status]}
            </span>
            <button
              aria-label={`Remove ${item.file.name}`}
              className={styles.removeQueueItem}
              disabled={isUploading}
              onClick={() => onRemove(item.id)}
              type="button"
            >
              <X aria-hidden="true" />
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export function DocumentUploadCard({
  collectionError,
  collectionOptions,
  collectionsUnavailable,
  fileInputRef,
  isUploading,
  onCollectionChange,
  onFilesSelected,
  onRemove,
  onUpload,
  queue,
  selectedCollectionId,
  serverError,
  submissionBlocked = false,
  successMessage,
}: DocumentUploadCardProps) {
  const [isDragging, setIsDragging] = useState(false);
  const validationMessage = getUploadValidationMessage(queue);
  const uploadDisabled =
    isUploading ||
    submissionBlocked ||
    queue.length === 0 ||
    hasBlockingUploadError(queue);
  const totalBytes = queue.reduce((total, item) => total + item.file.size, 0);

  const openFilePicker = () => fileInputRef.current?.click();
  const handleFiles = (files: FileList | null) => {
    if (isUploading) return;
    if (files?.length) onFilesSelected(Array.from(files));
  };
  const handleDrop = (event: DragEvent<HTMLButtonElement>) => {
    event.preventDefault();
    setIsDragging(false);
    handleFiles(event.dataTransfer.files);
  };
  const handleInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    handleFiles(event.target.files);
    event.target.value = "";
  };
  const invalidCount = queue.filter((item) => item.status !== "valid").length;
  const selectionSummary =
    queue.length === 0
      ? "No files selected"
      : queue.some((item) => item.status === "too-many-files")
        ? `${queue.length} files selected · remove ${
            queue.length - DOCUMENT_UPLOAD_LIMITS.maxFiles === 1
              ? "one file"
              : `${queue.length - DOCUMENT_UPLOAD_LIMITS.maxFiles} files`
          } to continue`
        : invalidCount > 0
          ? `${queue.length} ${queue.length === 1 ? "file" : "files"} selected · ${invalidCount} ${invalidCount === 1 ? "file needs" : "files need"} attention`
          : `${queue.length} ${queue.length === 1 ? "file" : "files"} selected · ${formatFileSize(totalBytes)} total`;

  return (
    <section aria-labelledby="document-upload-title" className={styles.uploadCard}>
      <div className={styles.uploadHeader}>
        <div>
          <h2 id="document-upload-title">Upload documents</h2>
          <p id="upload-constraints">
            Add 1–{DOCUMENT_UPLOAD_LIMITS.maxFiles} PDF, TXT, or MD files ·{" "}
            {DOCUMENT_UPLOAD_LIMITS.maxFileBytes / (1024 * 1024)} MB max each
          </p>
        </div>
        <CollectionButton disabled={uploadDisabled} onClick={onUpload} type="button">
          {isUploading
            ? "Uploading…"
            : queue.length > 0
              ? `Upload ${queue.length} ${queue.length === 1 ? "file" : "files"}`
              : "Upload files"}
        </CollectionButton>
      </div>
      <div className={styles.uploadAssignment}>
        <label htmlFor="documents-upload-collection">Add to collection</label>
        <div className={styles.uploadCollectionField}>
          <Select
            disabled={
              isUploading ||
              collectionsUnavailable ||
              collectionOptions.length === 0
            }
            onValueChange={onCollectionChange}
            value={selectedCollectionId ?? ""}
          >
            <SelectTrigger
              aria-describedby={
                collectionError
                  ? "documents-upload-collection-error"
                  : collectionsUnavailable
                    ? "documents-upload-collection-unavailable"
                    : undefined
              }
              aria-invalid={Boolean(collectionError)}
              aria-label="Choose a collection for this upload"
              aria-required="true"
              className={styles.collectionSelect}
              id="documents-upload-collection"
            >
              <SelectValue placeholder="Select collection" />
            </SelectTrigger>
            <SelectContent className={styles.collectionSelectContent}>
              {collectionOptions.map((collection) => (
                <SelectItem key={collection.id} value={collection.id}>
                  {collection.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {collectionError ? (
            <p
              className={styles.collectionError}
              id="documents-upload-collection-error"
              role="alert"
            >
              {collectionError}
            </p>
          ) : collectionsUnavailable ? (
            <p id="documents-upload-collection-unavailable">
              Collections are temporarily unavailable.
            </p>
          ) : null}
        </div>
      </div>
      <button
        aria-describedby="upload-constraints upload-selection-summary"
        aria-label="Choose documents or drop files here"
        className={`${styles.dropzone} ${isDragging ? styles.dropzoneDragging : ""}`}
        disabled={isUploading}
        onClick={openFilePicker}
        onDragEnter={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
            setIsDragging(false);
          }
        }}
        onDragOver={(event) => event.preventDefault()}
        onDrop={handleDrop}
        type="button"
      >
        <span className={styles.uploadIconHalo}>
          <FileUp aria-hidden="true" />
        </span>
        <strong>Drop files here or choose files</strong>
        <span aria-live="polite" id="upload-selection-summary">
          {selectionSummary}
        </span>
      </button>
      <input
        accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown"
        aria-label="Choose documents"
        className="sr-only"
        disabled={isUploading}
        multiple
        onChange={handleInputChange}
        ref={fileInputRef}
        type="file"
      />
      <UploadQueue
        isUploading={isUploading}
        onRemove={onRemove}
        queue={queue}
      />
      {validationMessage ? (
        <Alert className={styles.validationAlert} variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertDescription>{validationMessage}</AlertDescription>
        </Alert>
      ) : null}
      {serverError ? (
        <Alert className={styles.validationAlert} variant="destructive">
          <CircleAlert aria-hidden="true" />
          <AlertDescription>{serverError}</AlertDescription>
        </Alert>
      ) : null}
      {successMessage ? (
        <Alert className={styles.successAlert}>
          <CheckCircle2 aria-hidden="true" />
          <AlertDescription>{successMessage}</AlertDescription>
        </Alert>
      ) : null}
    </section>
  );
}
