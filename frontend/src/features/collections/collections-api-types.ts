export type CollectionApiRecord = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type PaginatedResponse<T> = {
  items: T[];
  limit: number;
  offset: number;
  total: number;
};

export type CollectionCreateInput = {
  name: string;
  description?: string | null;
};

export type CollectionUpdateInput = Partial<CollectionCreateInput>;

export type {
  DocumentRecord as CollectionDocument,
  DocumentStatus,
  DocumentUploadItem,
  DocumentUploadResult as DocumentUploadResponse,
} from "@/features/documents/types";
export type {
  Citation,
  QuestionAnswer,
  QuestionHistoryItem,
} from "@/features/questions/questions-api-types";
