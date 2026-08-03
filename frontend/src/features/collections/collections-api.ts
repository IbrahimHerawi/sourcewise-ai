import { apiRequest } from "@/lib/api";
import {
  invalidApiResponse,
  readApiArray,
  readApiDateTime,
  readApiInteger,
  readApiNullableString,
  readApiObject,
  readApiString,
  readApiUuid,
} from "@/lib/api-contract";
import {
  deleteDocumentApi,
  getDocumentApi,
  listDocumentsApi,
  uploadDocumentsApi,
} from "@/features/documents/documents-api";
import {
  mapDocumentRecord,
  mapDocumentUploadResult,
  mapPaginatedDocuments,
} from "@/features/documents/document-mappers";
import type {
  CollectionApiRecord,
  CollectionCreateInput,
  CollectionUpdateInput,
  PaginatedResponse,
  QuestionAnswer,
  QuestionHistoryItem,
} from "@/features/collections/collections-api-types";

const COLLECTIONS_CONTRACT = "Collections";

function paginationQuery(limit: number, offset: number) {
  return new URLSearchParams({ limit: String(limit), offset: String(offset) });
}

function parseCollection(value: unknown): CollectionApiRecord {
  const record = readApiObject(value, COLLECTIONS_CONTRACT);
  return {
    id: readApiUuid(record, "id", COLLECTIONS_CONTRACT),
    name: readApiString(record, "name", COLLECTIONS_CONTRACT),
    description: readApiNullableString(
      record,
      "description",
      COLLECTIONS_CONTRACT,
    ),
    created_at: readApiDateTime(record, "created_at", COLLECTIONS_CONTRACT),
    updated_at: readApiDateTime(record, "updated_at", COLLECTIONS_CONTRACT),
  };
}

function parseCollectionPage(
  value: unknown,
): PaginatedResponse<CollectionApiRecord> {
  const record = readApiObject(value, COLLECTIONS_CONTRACT);
  const limit = readApiInteger(record, "limit", COLLECTIONS_CONTRACT, 1);
  const offset = readApiInteger(record, "offset", COLLECTIONS_CONTRACT);
  const total = readApiInteger(record, "total", COLLECTIONS_CONTRACT);
  const items = readApiArray(record, "items", COLLECTIONS_CONTRACT).map(
    parseCollection,
  );
  if (
    items.length > limit ||
    items.length > Math.max(0, total - offset)
  ) {
    return invalidApiResponse(COLLECTIONS_CONTRACT);
  }
  return { items, limit, offset, total };
}

export async function getCollections(
  limit: number,
  offset: number,
  signal?: AbortSignal,
) {
  const response = await apiRequest<unknown>(
    `/collections?${paginationQuery(limit, offset)}`,
    { signal },
  );
  return parseCollectionPage(response);
}

export async function getCollection(
  collectionId: string,
  signal?: AbortSignal,
) {
  const response = await apiRequest<unknown>(`/collections/${collectionId}`, {
    signal,
  });
  return parseCollection(response);
}

export async function createCollection(
  input: CollectionCreateInput,
  signal?: AbortSignal,
) {
  const response = await apiRequest<unknown>("/collections", {
    method: "POST",
    body: JSON.stringify(input),
    signal,
  });
  return parseCollection(response);
}

export async function updateCollection(
  collectionId: string,
  input: CollectionUpdateInput,
  signal?: AbortSignal,
) {
  const response = await apiRequest<unknown>(`/collections/${collectionId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
    signal,
  });
  return parseCollection(response);
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
  return listDocumentsApi(
    { collectionId, limit, offset },
    signal,
  ).then(mapPaginatedDocuments);
}

export async function getDocument(documentId: string, signal?: AbortSignal) {
  return mapDocumentRecord(await getDocumentApi(documentId, signal));
}

export function deleteDocument(documentId: string, signal?: AbortSignal) {
  return deleteDocumentApi(documentId, signal);
}

export function uploadCollectionDocuments(
  collectionId: string,
  files: readonly File[],
  signal?: AbortSignal,
) {
  return uploadDocumentsApi({ collectionId, files }, signal).then(
    mapDocumentUploadResult,
  );
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
