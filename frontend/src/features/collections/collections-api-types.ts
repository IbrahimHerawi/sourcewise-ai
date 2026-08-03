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

export type Citation = {
  rank: number;
  document_id: string;
  document_filename: string;
  chunk_id: string;
  chunk_index: number;
  excerpt: string;
  distance: number;
};

export type QuestionAnswer = {
  question_id: string;
  collection_id: string | null;
  answer: string;
  citations: Citation[];
  created_at: string;
  provider: "openai" | "ollama" | null;
  model: string | null;
};

export type QuestionHistoryItem = QuestionAnswer & {
  question: string;
};
