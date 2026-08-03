import type {
  DocumentApiRecord,
  DocumentUploadApiResponse,
  PaginatedDocumentApiResponse,
} from "./documents-api-types";
import type {
  DocumentRecord,
  DocumentStatus,
  DocumentUploadResult,
  PaginatedDocuments,
} from "./types";

const DOCUMENT_STATUSES = new Set<DocumentStatus>([
  "PENDING",
  "PROCESSING",
  "READY",
  "FAILED",
  "UNKNOWN",
]);

export function mapDocumentStatus(status: string): DocumentStatus {
  return DOCUMENT_STATUSES.has(status as DocumentStatus)
    ? (status as DocumentStatus)
    : "UNKNOWN";
}

export function mapDocumentRecord(document: DocumentApiRecord): DocumentRecord {
  return {
    ...document,
    status: mapDocumentStatus(document.status),
  };
}

export function mapPaginatedDocuments(
  response: PaginatedDocumentApiResponse,
): PaginatedDocuments {
  return {
    ...response,
    items: response.items.map(mapDocumentRecord),
  };
}

export function mapDocumentUploadResult(
  response: DocumentUploadApiResponse,
): DocumentUploadResult {
  return {
    items: response.items.map((item) => ({
      ...item,
      status: mapDocumentStatus(item.status),
    })),
  };
}
