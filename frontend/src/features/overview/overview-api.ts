import { listAllCollectionsApi } from "@/features/collections/collections-api";
import { mapDocumentRecord } from "@/features/documents/document-mappers";
import { listDocumentsApi } from "@/features/documents/documents-api";
import { listQuestionHistoryApi } from "@/features/questions/questions-api";
import { apiRequest } from "@/lib/api";
import {
  readApiInteger,
  readApiObject,
} from "@/lib/api-contract";
import type { OverviewCounts, OverviewData } from "./overview-api-types";

const OVERVIEW_CONTRACT = "overview";
const RECENT_DOCUMENT_LIMIT = 5;
const RECENT_QUESTION_LIMIT = 3;

function parseOverviewCounts(value: unknown): OverviewCounts {
  const record = readApiObject(value, OVERVIEW_CONTRACT);
  return {
    total_documents: readApiInteger(
      record,
      "total_documents",
      OVERVIEW_CONTRACT,
    ),
    total_questions: readApiInteger(
      record,
      "total_questions",
      OVERVIEW_CONTRACT,
    ),
    total_collections: readApiInteger(
      record,
      "total_collections",
      OVERVIEW_CONTRACT,
    ),
  };
}

export async function getOverviewCountsApi(
  signal?: AbortSignal,
): Promise<OverviewCounts> {
  const response = await apiRequest<unknown>("/auth/overview", { signal });
  return parseOverviewCounts(response);
}

export async function getOverviewDataApi(
  signal?: AbortSignal,
): Promise<OverviewData> {
  const [counts, documents, questions, collections] = await Promise.all([
    getOverviewCountsApi(signal),
    listDocumentsApi(
      { collectionId: null, limit: RECENT_DOCUMENT_LIMIT, offset: 0 },
      signal,
    ),
    listQuestionHistoryApi(
      { collectionId: null, limit: RECENT_QUESTION_LIMIT, offset: 0 },
      signal,
    ),
    listAllCollectionsApi(signal),
  ]);

  return {
    counts,
    collections,
    recentDocuments: documents.items.map(mapDocumentRecord),
    recentQuestions: questions.items,
  };
}
