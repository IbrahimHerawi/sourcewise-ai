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

export function mapDocumentStatus(status: string): DocumentStatus {
  switch (status) {
    case "PENDING":
    case "PROCESSING":
    case "READY":
    case "FAILED":
      return status;
    default:
      return "UNKNOWN";
  }
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
