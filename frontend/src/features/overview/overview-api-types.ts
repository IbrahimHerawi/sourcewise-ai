import type { CollectionApiRecord } from "@/features/collections/collections-api-types";
import type { DocumentRecord } from "@/features/documents/types";
import type { QuestionHistoryItem } from "@/features/questions/questions-api-types";

export type OverviewCounts = {
  total_documents: number;
  total_questions: number;
  total_collections: number;
};

export type OverviewData = {
  counts: OverviewCounts;
  collections: CollectionApiRecord[];
  recentDocuments: DocumentRecord[];
  recentQuestions: QuestionHistoryItem[];
};
