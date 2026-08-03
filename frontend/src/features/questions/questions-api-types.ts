export type QuestionProvider = "openai" | "ollama";

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
  provider: QuestionProvider | null;
  model: string | null;
};

export type QuestionHistoryItem = QuestionAnswer & {
  question: string;
};

export type PaginatedQuestionHistory = {
  items: QuestionHistoryItem[];
  limit: number;
  offset: number;
  total: number;
};

export type AskQuestionApiInput = {
  collectionId: string | null;
  question: string;
};

export type QuestionHistoryApiInput = {
  collectionId?: string | null;
  limit: number;
  offset: number;
};
