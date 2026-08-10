export type DocumentStatus =
  | "PENDING"
  | "PROCESSING"
  | "READY"
  | "FAILED"
  | "UNKNOWN";

export type UploadQueueStatus =
  | "valid"
  | "empty-file"
  | "invalid-type"
  | "too-large"
  | "too-many-files";

export type UploadQueueItem = {
  file: File;
  id: string;
  message?: string;
  status: UploadQueueStatus;
};

export type DocumentRecord = {
  id: string;
  collection_id: string | null;
  filename: string;
  original_extension: string;
  content_type: string;
  size_bytes: number;
  status: DocumentStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type DocumentCollection = {
  id: string;
  name: string;
};

export type PaginatedDocuments = {
  items: DocumentRecord[];
  limit: number;
  offset: number;
  total: number;
};

export type DocumentUploadItem = {
  document_id: string;
  filename: string;
  collection_id: string | null;
  status: DocumentStatus;
};

export type DocumentUploadResult = {
  items: DocumentUploadItem[];
};

export type DocumentDialogState =
  | { type: "details"; document: DocumentRecord }
  | { type: "delete"; document: DocumentRecord }
  | null;
