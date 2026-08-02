import { apiRequest } from "@/lib/api";
import type {
  CollectionApiRecord,
  CollectionCreateInput,
  CollectionDocument,
  CollectionUpdateInput,
  DocumentUploadResponse,
  PaginatedResponse,
  QuestionAnswer,
  QuestionHistoryItem,
} from "@/features/collections/collections-api-types";

function paginationQuery(limit: number, offset: number) {
  return new URLSearchParams({ limit: String(limit), offset: String(offset) });
}

export function getCollections(limit: number, offset: number, signal?: AbortSignal) {
  return apiRequest<PaginatedResponse<CollectionApiRecord>>(
    `/collections?${paginationQuery(limit, offset)}`,
    { signal },
  );
}

export function getCollection(collectionId: string, signal?: AbortSignal) {
  return apiRequest<CollectionApiRecord>(`/collections/${collectionId}`, { signal });
}

export function createCollection(input: CollectionCreateInput, signal?: AbortSignal) {
  return apiRequest<CollectionApiRecord>("/collections", {
    method: "POST",
    body: JSON.stringify(input),
    signal,
  });
}

export function updateCollection(
  collectionId: string,
  input: CollectionUpdateInput,
  signal?: AbortSignal,
) {
  return apiRequest<CollectionApiRecord>(`/collections/${collectionId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
    signal,
  });
}

export function deleteCollection(collectionId: string, signal?: AbortSignal) {
  return apiRequest<Record<string, never>>(`/collections/${collectionId}`, {
    method: "DELETE",
    signal,
  });
}

export function getCollectionDocuments(
  collectionId: string,
  limit: number,
  offset: number,
  signal?: AbortSignal,
) {
  const query = paginationQuery(limit, offset);
  query.set("collection_id", collectionId);
  return apiRequest<PaginatedResponse<CollectionDocument>>(
    `/documents?${query}`,
    { signal },
  );
}

export function getDocument(documentId: string, signal?: AbortSignal) {
  return apiRequest<CollectionDocument>(`/documents/${documentId}`, { signal });
}

export function deleteDocument(documentId: string, signal?: AbortSignal) {
  return apiRequest<Record<string, never>>(`/documents/${documentId}`, {
    method: "DELETE",
    signal,
  });
}

export function uploadCollectionDocuments(
  collectionId: string,
  files: readonly File[],
  signal?: AbortSignal,
) {
  const body = new FormData();
  files.forEach((file) => body.append("files", file));
  body.append("collection_id", collectionId);
  return apiRequest<DocumentUploadResponse>("/documents/upload", {
    method: "POST",
    body,
    signal,
  });
}

export function askCollection(
  collectionId: string,
  question: string,
  signal?: AbortSignal,
) {
  return apiRequest<QuestionAnswer>("/questions/ask", {
    method: "POST",
    body: JSON.stringify({ question, collection_id: collectionId }),
    signal,
  });
}

export function getCollectionHistory(
  collectionId: string,
  limit: number,
  offset: number,
  signal?: AbortSignal,
) {
  const query = paginationQuery(limit, offset);
  query.set("collection_id", collectionId);
  return apiRequest<PaginatedResponse<QuestionHistoryItem>>(
    `/questions/history?${query}`,
    { signal },
  );
}

export function getQuestionHistoryItem(questionId: string, signal?: AbortSignal) {
  return apiRequest<QuestionHistoryItem>(`/questions/history/${questionId}`, { signal });
}

export function deleteQuestionHistoryItem(questionId: string, signal?: AbortSignal) {
  return apiRequest<Record<string, never>>(`/questions/history/${questionId}`, {
    method: "DELETE",
    signal,
  });
}
