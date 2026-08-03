import { apiRequest } from "@/lib/api";
import {
  invalidApiResponse,
  readApiArray,
  readApiDateTime,
  readApiInteger,
  readApiNullableString,
  readApiNullableUuid,
  readApiObject,
  readApiString,
  readApiUuid,
} from "@/lib/api-contract";
import type {
  DocumentApiRecord,
  DocumentsListApiInput,
  DocumentsUploadApiInput,
  DocumentUploadApiItem,
  DocumentUploadApiResponse,
  PaginatedDocumentApiResponse,
} from "./documents-api-types";

const DOCUMENT_CONTRACT = "Documents";

function parseDocument(value: unknown): DocumentApiRecord {
  const record = readApiObject(value, DOCUMENT_CONTRACT);
  return {
    id: readApiUuid(record, "id", DOCUMENT_CONTRACT),
    collection_id: readApiNullableUuid(
      record,
      "collection_id",
      DOCUMENT_CONTRACT,
    ),
    filename: readApiString(record, "filename", DOCUMENT_CONTRACT),
    original_extension: readApiString(
      record,
      "original_extension",
      DOCUMENT_CONTRACT,
    ),
    content_type: readApiString(record, "content_type", DOCUMENT_CONTRACT),
    size_bytes: readApiInteger(record, "size_bytes", DOCUMENT_CONTRACT),
    status: readApiString(record, "status", DOCUMENT_CONTRACT),
    error_message: readApiNullableString(
      record,
      "error_message",
      DOCUMENT_CONTRACT,
    ),
    created_at: readApiDateTime(record, "created_at", DOCUMENT_CONTRACT),
    updated_at: readApiDateTime(record, "updated_at", DOCUMENT_CONTRACT),
  };
}

function parseDocumentList(value: unknown): PaginatedDocumentApiResponse {
  const record = readApiObject(value, DOCUMENT_CONTRACT);
  const limit = readApiInteger(record, "limit", DOCUMENT_CONTRACT, 1);
  const offset = readApiInteger(record, "offset", DOCUMENT_CONTRACT);
  const total = readApiInteger(record, "total", DOCUMENT_CONTRACT);
  const items = readApiArray(record, "items", DOCUMENT_CONTRACT).map(
    parseDocument,
  );
  if (
    items.length > limit ||
    items.length > Math.max(0, total - offset)
  ) {
    return invalidApiResponse(DOCUMENT_CONTRACT);
  }
  return { items, limit, offset, total };
}

function parseUploadItem(value: unknown): DocumentUploadApiItem {
  const record = readApiObject(value, DOCUMENT_CONTRACT);
  return {
    document_id: readApiUuid(record, "document_id", DOCUMENT_CONTRACT),
    filename: readApiString(record, "filename", DOCUMENT_CONTRACT),
    collection_id: readApiNullableUuid(
      record,
      "collection_id",
      DOCUMENT_CONTRACT,
    ),
    status: readApiString(record, "status", DOCUMENT_CONTRACT),
  };
}

function parseUploadResponse(
  value: unknown,
  expectedItems: number,
): DocumentUploadApiResponse {
  const record = readApiObject(value, DOCUMENT_CONTRACT);
  const items = readApiArray(record, "items", DOCUMENT_CONTRACT).map(
    parseUploadItem,
  );
  if (items.length !== expectedItems) {
    return invalidApiResponse(DOCUMENT_CONTRACT);
  }
  return { items };
}

export async function listDocumentsApi(
  input: DocumentsListApiInput,
  signal?: AbortSignal,
): Promise<PaginatedDocumentApiResponse> {
  const query = new URLSearchParams({
    limit: String(input.limit),
    offset: String(input.offset),
  });
  if (input.collectionId) query.set("collection_id", input.collectionId);
  const response = await apiRequest<unknown>(`/documents?${query}`, { signal });
  const page = parseDocumentList(response);
  if (page.limit !== input.limit || page.offset !== input.offset) {
    return invalidApiResponse(DOCUMENT_CONTRACT);
  }
  return page;
}

export async function getDocumentApi(
  documentId: string,
  signal?: AbortSignal,
): Promise<DocumentApiRecord> {
  const response = await apiRequest<unknown>(`/documents/${documentId}`, {
    signal,
  });
  return parseDocument(response);
}

export async function uploadDocumentsApi(
  input: DocumentsUploadApiInput,
  signal?: AbortSignal,
): Promise<DocumentUploadApiResponse> {
  const body = new FormData();
  input.files.forEach((file) => body.append("files", file));
  if (input.collectionId) body.append("collection_id", input.collectionId);
  const response = await apiRequest<unknown>("/documents/upload", {
    method: "POST",
    body,
    signal,
  });
  return parseUploadResponse(response, input.files.length);
}

export function deleteDocumentApi(
  documentId: string,
  signal?: AbortSignal,
): Promise<Record<string, never>> {
  return apiRequest<Record<string, never>>(`/documents/${documentId}`, {
    method: "DELETE",
    signal,
  });
}
