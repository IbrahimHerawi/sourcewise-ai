export type DocumentApiRecord = {
  id: string;
  collection_id: string | null;
  filename: string;
  original_extension: string;
  content_type: string;
  size_bytes: number;
  status: string;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type PaginatedDocumentApiResponse = {
  items: DocumentApiRecord[];
  limit: number;
  offset: number;
  total: number;
};

export type DocumentUploadApiItem = {
  document_id: string;
  filename: string;
  collection_id: string | null;
  status: string;
};

export type DocumentUploadApiResponse = {
  items: DocumentUploadApiItem[];
};

export type DocumentsListApiInput = {
  collectionId?: string | null;
  limit: number;
  offset: number;
};

export type DocumentsUploadApiInput = {
  collectionId: string | null;
  files: readonly File[];
};
