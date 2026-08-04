import type { UploadQueueItem, UploadQueueStatus } from "./types";

export const DOCUMENT_UPLOAD_LIMITS = {
  acceptedExtensions: [".pdf", ".txt", ".md"],
  maxFileBytes: 10 * 1024 * 1024,
  maxFiles: 3,
} as const;

export type SupportedDocumentExtension =
  (typeof DOCUMENT_UPLOAD_LIMITS.acceptedExtensions)[number];

export const DOCUMENT_FILE_TYPE_LABELS: Readonly<
  Record<SupportedDocumentExtension, string>
> = {
  ".pdf": "PDF",
  ".txt": "TXT",
  ".md": "MD",
};

const ACCEPTED_EXTENSION_SET = new Set<string>(
  DOCUMENT_UPLOAD_LIMITS.acceptedExtensions,
);

export function isSupportedDocumentExtension(
  value: string,
): value is SupportedDocumentExtension {
  return ACCEPTED_EXTENSION_SET.has(value);
}

function fileExtension(filename: string): string {
  const extensionIndex = filename.lastIndexOf(".");
  return extensionIndex < 0 ? "" : filename.slice(extensionIndex).toLowerCase();
}

function queueItemId(file: File, index: number): string {
  return `${file.name}-${file.size}-${file.lastModified}-${index}`;
}

function validateFile(file: File, index: number, total: number): {
  message?: string;
  status: UploadQueueStatus;
} {
  if (index >= DOCUMENT_UPLOAD_LIMITS.maxFiles && total > DOCUMENT_UPLOAD_LIMITS.maxFiles) {
    return {
      message: "Remove this file to keep the batch within the three-file limit.",
      status: "too-many-files",
    };
  }

  if (!ACCEPTED_EXTENSION_SET.has(fileExtension(file.name))) {
    return {
      message: "Unsupported type. Choose a PDF, TXT, or MD file.",
      status: "invalid-type",
    };
  }

  if (file.size === 0) {
    return {
      message: "Empty files cannot be uploaded.",
      status: "empty-file",
    };
  }

  if (file.size > DOCUMENT_UPLOAD_LIMITS.maxFileBytes) {
    return {
      message: "This file exceeds the 10 MB limit.",
      status: "too-large",
    };
  }

  return { status: "valid" };
}

export function createUploadQueue(files: readonly File[]): UploadQueueItem[] {
  return files.map((file, index) => ({
    file,
    id: queueItemId(file, index),
    ...validateFile(file, index, files.length),
  }));
}

export function getUploadValidationMessage(
  queue: readonly UploadQueueItem[],
): string | undefined {
  if (queue.some((item) => item.status === "too-many-files")) {
    return "Upload blocked — Select 1–3 PDF, TXT, or MD files. Each file must be 10 MB or less.";
  }

  const invalidType = queue.find((item) => item.status === "invalid-type");
  if (invalidType) {
    return `Upload blocked — ${invalidType.file.name} is not a supported file type.`;
  }

  const empty = queue.find((item) => item.status === "empty-file");
  if (empty) {
    return `Upload blocked — ${empty.file.name} is empty.`;
  }

  const oversized = queue.find((item) => item.status === "too-large");
  if (oversized) {
    return `Upload blocked — ${oversized.file.name} is larger than the 10 MB limit.`;
  }

  return undefined;
}

export function hasBlockingUploadError(queue: readonly UploadQueueItem[]): boolean {
  return queue.some((item) => item.status !== "valid");
}
